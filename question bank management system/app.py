from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, make_response, session, flash
)
import sqlite3
import os
import random
from xhtml2pdf import pisa
from io import BytesIO
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd  # For Excel import/export

app = Flask(__name__)
app.secret_key = "change_this_secret_key"   # IMPORTANT: change for security
DB_NAME = "question_bank.db"


# ---------- DB HELPER ----------

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # subjects (one record per subject)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)

    # modules / units inside a subject
    cur.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            module_no INTEGER NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """)

    # topics inside a module
    cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (module_id) REFERENCES modules(id)
        )
    """)

    # questions inside a topic
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            marks INTEGER NOT NULL,
            difficulty TEXT NOT NULL,           -- Easy / Medium / Hard
            cognitive_level TEXT NOT NULL,      -- Remember / Understand / Apply / Analyze / Evaluate / Create
            co TEXT,                            -- e.g. CO1, CO2
            po TEXT,                            -- e.g. PO1, PO2
            created_by INTEGER,                 -- user id (faculty/admin)
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    # users (login accounts)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL                 -- 'admin' or 'faculty'
        )
    """)

    # Activity logs (who did what operations)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # create default admin if not exists
    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        admin_pass = generate_password_hash("admin123")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", admin_pass, "admin"),
        )
        conn.commit()

    conn.close()


# Initialize DB
if not os.path.exists(DB_NAME):
    init_db()
else:
    init_db()


# ---------- AUTH HELPERS ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "error")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def add_log(user_id, action):
    if not user_id:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()


# ---------- ROUTES: AUTH ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Logged in as {user['username']} ({user['role']})", "success")
            add_log(user["id"], "Logged in")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    user_id = session.get("user_id")
    add_log(user_id, "Logged out")
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# (Optional) simple user registration for faculty (admin can create)
@app.route("/create-user", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        role = request.form.get("role", "faculty")

        if not username or not password:
            flash("Username and password required.", "error")
            return redirect(url_for("create_user"))

        conn = get_db()
        cur = conn.cursor()
        try:
            pw_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, pw_hash, role),
            )
            conn.commit()
            flash("User created successfully.", "success")
            add_log(session.get("user_id"), f"Created user {username} ({role})")
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
        finally:
            conn.close()

    return render_template("create_user.html")


# ---------- ROUTES: CORE PAGES ----------

@app.route("/")
@login_required
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM subjects")
    subjects_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM questions")
    questions_count = cur.fetchone()["c"]
    conn.close()
    return render_template(
        "index.html",
        subjects_count=subjects_count,
        questions_count=questions_count,
    )


# ---- SUBJECTS ----

@app.route("/subjects", methods=["GET", "POST"])
@admin_required
def subjects():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            code = request.form["code"].strip()
            name = request.form["name"].strip()
            if code and name:
                cur.execute(
                    "INSERT INTO subjects (code, name) VALUES (?, ?)", (code, name)
                )
                conn.commit()
                flash("Subject added.", "success")
                add_log(session.get("user_id"), f"Added subject {code} - {name}")

        elif action == "edit":
            subject_id = request.form["subject_id"]
            code = request.form["code"].strip()
            name = request.form["name"].strip()
            cur.execute(
                "UPDATE subjects SET code=?, name=? WHERE id=?",
                (code, name, subject_id),
            )
            conn.commit()
            flash("Subject updated.", "success")
            add_log(session.get("user_id"), f"Edited subject ID {subject_id}")

        elif action == "delete":
            subject_id = request.form["subject_id"]
            cur.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
            conn.commit()
            flash("Subject deleted.", "success")
            add_log(session.get("user_id"), f"Deleted subject ID {subject_id}")

    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()
    conn.close()
    return render_template("subjects.html", subjects=subjects_list)


# ---- MODULES / UNITS ----

@app.route("/subjects/<int:subject_id>/modules", methods=["GET", "POST"])
@admin_required
def modules(subject_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
    subject = cur.fetchone()

    if not subject:
        conn.close()
        flash("Subject not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            module_no = request.form["module_no"]
            title = request.form["title"].strip()
            if module_no and title:
                cur.execute(
                    "INSERT INTO modules (subject_id, module_no, title) VALUES (?, ?, ?)",
                    (subject_id, module_no, title),
                )
                conn.commit()
                flash("Module added.", "success")
                add_log(session.get("user_id"),
                        f"Added module {module_no} - {title} in subject {subject['code']}")

        elif action == "edit":
            module_id = request.form["module_id"]
            module_no = request.form["module_no"]
            title = request.form["title"].strip()
            cur.execute(
                "UPDATE modules SET module_no=?, title=? WHERE id=?",
                (module_no, title, module_id),
            )
            conn.commit()
            flash("Module updated.", "success")
            add_log(session.get("user_id"), f"Edited module ID {module_id}")

        elif action == "delete":
            module_id = request.form["module_id"]
            cur.execute("DELETE FROM modules WHERE id=?", (module_id,))
            conn.commit()
            flash("Module deleted.", "success")
            add_log(session.get("user_id"), f"Deleted module ID {module_id}")

    cur.execute(
        "SELECT * FROM modules WHERE subject_id=? ORDER BY module_no", (subject_id,)
    )
    modules_list = cur.fetchall()
    conn.close()

    return render_template("modules.html", subject=subject, modules=modules_list)


# ---- TOPICS ----

@app.route("/modules/<int:module_id>/topics", methods=["GET", "POST"])
@admin_required
def topics(module_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT m.*, s.name AS subject_name, s.code AS subject_code "
        "FROM modules m JOIN subjects s ON m.subject_id = s.id WHERE m.id=?",
        (module_id,),
    )
    module = cur.fetchone()

    if not module:
        conn.close()
        flash("Module not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form["name"].strip()
            if name:
                cur.execute(
                    "INSERT INTO topics (module_id, name) VALUES (?, ?)",
                    (module_id, name),
                )
                conn.commit()
                flash("Topic added.", "success")
                add_log(session.get("user_id"),
                        f"Added topic '{name}' in module {module['module_no']}")

        elif action == "edit":
            topic_id = request.form["topic_id"]
            name = request.form["name"].strip()
            cur.execute("UPDATE topics SET name=? WHERE id=?", (name, topic_id))
            conn.commit()
            flash("Topic updated.", "success")
            add_log(session.get("user_id"), f"Edited topic ID {topic_id}")

        elif action == "delete":
            topic_id = request.form["topic_id"]
            cur.execute("DELETE FROM topics WHERE id=?", (topic_id,))
            conn.commit()
            flash("Topic deleted.", "success")
            add_log(session.get("user_id"), f"Deleted topic ID {topic_id}")

    cur.execute("SELECT * FROM topics WHERE module_id=? ORDER BY id", (module_id,))
    topics_list = cur.fetchall()
    conn.close()
    return render_template("topics.html", module=module, topics=topics_list)


# ---- ANALYTICS (for Chart.js) ----

@app.route("/analytics")
@admin_required
def analytics():
    conn = get_db()
    cur = conn.cursor()

    # Questions count by difficulty
    cur.execute("SELECT difficulty, COUNT(*) AS c FROM questions GROUP BY difficulty")
    difficulty = {row["difficulty"]: row["c"] for row in cur.fetchall()}

    # Questions count by modules
    cur.execute("""
        SELECT m.module_no, COUNT(q.id) AS c
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        GROUP BY m.module_no
        ORDER BY m.module_no
    """)
    module_data = [(row["module_no"], row["c"]) for row in cur.fetchall()]

    conn.close()

    return render_template(
        "analytics.html",
        difficulty=difficulty,
        module_labels=[m[0] for m in module_data],
        module_values=[m[1] for m in module_data]
    )


# ---- EXPORT EXCEL ----

@app.route("/export-excel")
@admin_required
def export_excel():
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT q.id, q.question_text, q.marks, q.difficulty, q.cognitive_level,
               q.co, q.po, t.name AS topic, m.module_no, s.code AS subject
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
    """, conn)
    conn.close()

    file_path = "questionbank_export.xlsx"
    df.to_excel(file_path, index=False)
    add_log(session.get("user_id"), "Exported question bank to Excel")

    return send_file(file_path, as_attachment=True)


# ---- IMPORT EXCEL ----

@app.route("/import-excel", methods=["GET", "POST"])
@admin_required
def import_excel():
    if request.method == "POST":
        file = request.files["file"]
        if not file:
            flash("Please select a file.", "error")
            return redirect(url_for("import_excel"))

        df = pd.read_excel(file)

        conn = get_db()
        cur = conn.cursor()

        for _, row in df.iterrows():
            qt = str(row.get("question_text", "")).strip()
            if not qt:
                continue

            # Basic duplicate skip
            cur.execute("SELECT id FROM questions WHERE question_text=?", (qt,))
            if cur.fetchone():
                continue

            marks = int(row.get("marks", 2))
            difficulty = str(row.get("difficulty", "Medium"))
            cognitive = str(row.get("cognitive_level", "Understand"))
            co = str(row.get("co", "")).strip()
            po = str(row.get("po", "")).strip()

            cur.execute("""
                INSERT INTO questions (topic_id, question_text, marks, difficulty, cognitive_level, co, po)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, qt, marks, difficulty, cognitive, co, po))  # default topic_id=1 or adjust logic

        conn.commit()
        conn.close()
        flash("Questions imported successfully from Excel!", "success")
        add_log(session.get("user_id"), "Imported questions from Excel")
        return redirect(url_for("index"))

    return render_template("import_excel.html")


# ---- QUESTIONS ----

@app.route("/topics/<int:topic_id>/questions", methods=["GET", "POST"])
@login_required
def questions(topic_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT t.*, m.module_no, m.title AS module_title,
               s.code AS subject_code, s.name AS subject_name
        FROM topics t
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE t.id=?
    """,
        (topic_id,),
    )
    topic = cur.fetchone()

    if not topic:
        conn.close()
        flash("Topic not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")
        user_id = session.get("user_id")

        if action == "add":
            question_text = request.form["question_text"].strip()
            marks = request.form.get("marks", 2)
            difficulty = request.form.get("difficulty", "Medium")
            cognitive_level = request.form.get("cognitive_level", "Understand")
            co = request.form.get("co", "").strip()
            po = request.form.get("po", "").strip()

            if question_text:
                # DUPLICATE CHECK
                cur.execute(
                    "SELECT id FROM questions WHERE question_text=? AND topic_id=?",
                    (question_text, topic_id)
                )
                if cur.fetchone():
                    flash("Duplicate question found! Please add a different question.", "error")
                else:
                    cur.execute(
                        """
                        INSERT INTO questions (topic_id, question_text, marks, difficulty,
                                               cognitive_level, co, po, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            topic_id,
                            question_text,
                            marks,
                            difficulty,
                            cognitive_level,
                            co,
                            po,
                            user_id,
                        ),
                    )
                    conn.commit()
                    flash("Question added.", "success")
                    add_log(user_id, f"Added question in topic {topic_id}")

        elif action == "delete":
            q_id = request.form["question_id"]
            # Admin can delete any; faculty can delete only own questions
            if session.get("role") == "admin":
                cur.execute("DELETE FROM questions WHERE id=?", (q_id,))
            else:
                cur.execute(
                    "DELETE FROM questions WHERE id=? AND created_by=?",
                    (q_id, user_id),
                )
            conn.commit()
            flash("Question deleted (if you had permission).", "success")
            add_log(user_id, f"Deleted question ID {q_id}")

    cur.execute(
        "SELECT q.*, u.username as author FROM questions q "
        "LEFT JOIN users u ON q.created_by = u.id "
        "WHERE q.topic_id=? ORDER BY q.id DESC",
        (topic_id,),
    )
    questions_list = cur.fetchall()
    conn.close()

    return render_template("questions.html", topic=topic, questions=questions_list)


@app.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT q.*, t.name AS topic_name, t.id AS topic_id,
               m.module_no, m.title AS module_title,
               s.code AS subject_code, s.name AS subject_name
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE q.id=?
    """,
        (question_id,),
    )
    question = cur.fetchone()

    if not question:
        conn.close()
        flash("Question not found.", "error")
        return redirect(url_for("subjects"))

    user_id = session.get("user_id")
    role = session.get("role")

    # Only admin or creator can edit
    if role != "admin" and question["created_by"] != user_id:
        conn.close()
        flash("You do not have permission to edit this question.", "error")
        return redirect(url_for("questions", topic_id=question["topic_id"]))

    if request.method == "POST":
        question_text = request.form["question_text"].strip()
        marks = request.form.get("marks", 2)
        difficulty = request.form.get("difficulty", "Medium")
        cognitive_level = request.form.get("cognitive_level", "Understand")
        co = request.form.get("co", "").strip()
        po = request.form.get("po", "").strip()

        cur.execute(
            """
            UPDATE questions
            SET question_text=?, marks=?, difficulty=?,
                cognitive_level=?, co=?, po=?
            WHERE id=?
        """,
            (
                question_text,
                marks,
                difficulty,
                cognitive_level,
                co,
                po,
                question_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Question updated.", "success")
        add_log(user_id, f"Edited question ID {question_id}")
        return redirect(url_for("questions", topic_id=question["topic_id"]))

    conn.close()
    return render_template("edit_question.html", question=question)


# ---- SEARCH ----

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()

    results = []
    selected_subject = None
    selected_module = None
    selected_difficulty = None

    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        module_no = request.form.get("module_no")
        difficulty = request.form.get("difficulty")

        selected_difficulty = difficulty

        query = """
            SELECT q.*, t.name AS topic_name, m.module_no, m.title AS module_title,
                   s.code AS subject_code
            FROM questions q
            JOIN topics t ON q.topic_id = t.id
            JOIN modules m ON t.module_id = m.id
            JOIN subjects s ON m.subject_id = s.id
            WHERE 1=1
        """
        params = []

        if subject_id and subject_id != "all":
            query += " AND s.id = ?"
            params.append(subject_id)
            cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
            selected_subject = cur.fetchone()

        if module_no:
            query += " AND m.module_no = ?"
            params.append(module_no)
            selected_module = module_no

        if difficulty and difficulty != "all":
            query += " AND q.difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY s.code, m.module_no, t.name"
        cur.execute(query, tuple(params))
        results = cur.fetchall()

    conn.close()
    return render_template(
        "search.html",
        subjects=subjects_list,
        results=results,
        selected_subject=selected_subject,
        selected_module=selected_module,
        selected_difficulty=selected_difficulty,
    )


# ---- QUESTION PAPER GENERATION ----

def generate_question_set(subject_id, total_questions, difficulty_distribution):
    conn = get_db()
    cur = conn.cursor()

    paper_questions = []

    for diff, count in difficulty_distribution.items():
        if count <= 0:
            continue
        cur.execute(
            """
            SELECT q.*, t.name AS topic_name, m.module_no, s.code AS subject_code
            FROM questions q
            JOIN topics t ON q.topic_id = t.id
            JOIN modules m ON t.module_id = m.id
            JOIN subjects s ON m.subject_id = s.id
            WHERE s.id = ? AND q.difficulty = ?
        """,
            (subject_id, diff),
        )
        rows = cur.fetchall()
        rows = list(rows)
        random.shuffle(rows)
        paper_questions.extend(rows[:count])

    conn.close()
    return paper_questions


def render_pdf_from_template(template_name, **context):
    html = render_template(template_name, **context)
    pdf_io = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_io)
    if pisa_status.err:
        return None
    pdf_io.seek(0)
    return pdf_io


@app.route("/generate-paper", methods=["GET", "POST"])
@login_required
def generate_paper():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()
    conn.close()

    if request.method == "POST":
        subject_id = int(request.form["subject_id"])
        exam_type = request.form.get("exam_type", "Internal")

        easy_q = int(request.form.get("easy_q", 2))
        med_q = int(request.form.get("med_q", 3))
        hard_q = int(request.form.get("hard_q", 1))

        total_q = easy_q + med_q + hard_q

        paper_questions = generate_question_set(
            subject_id,
            total_q,
            {"Easy": easy_q, "Medium": med_q, "Hard": hard_q},
        )

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
        subject = cur.fetchone()
        conn.close()

        pdf_io = render_pdf_from_template(
            "paper_template.html",
            subject=subject,
            exam_type=exam_type,
            questions=paper_questions,
        )

        if pdf_io is None:
            return "Error generating PDF", 500

        response = make_response(pdf_io.read())
        response.headers["Content-Type"] = "application/pdf"
        response.headers[
            "Content-Disposition"
        ] = f"attachment; filename=question_paper_{subject['code']}.pdf"
        return response

    return render_template("generate_paper.html", subjects=subjects_list)


# ---- LOGS VIEW ----

@app.route("/logs")
@admin_required
def logs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.action, l.timestamp, u.username
        FROM logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC
    """)
    data = cur.fetchall()
    conn.close()
    return render_template("logs.html", logs=data)


if __name__ == "__main__":
    app.run(debug=True)
from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, make_response, session, flash
)
import sqlite3
import os
import random
from xhtml2pdf import pisa
from io import BytesIO
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd  # For Excel import/export

app = Flask(__name__)
app.secret_key = "change_this_secret_key"   # IMPORTANT: change for security
DB_NAME = "question_bank.db"


# ---------- DB HELPER ----------

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # subjects (one record per subject)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)

    # modules / units inside a subject
    cur.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            module_no INTEGER NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """)

    # topics inside a module
    cur.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (module_id) REFERENCES modules(id)
        )
    """)

    # questions inside a topic
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            marks INTEGER NOT NULL,
            difficulty TEXT NOT NULL,           -- Easy / Medium / Hard
            cognitive_level TEXT NOT NULL,      -- Remember / Understand / Apply / Analyze / Evaluate / Create
            co TEXT,                            -- e.g. CO1, CO2
            po TEXT,                            -- e.g. PO1, PO2
            created_by INTEGER,                 -- user id (faculty/admin)
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)

    # users (login accounts)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL                 -- 'admin' or 'faculty'
        )
    """)

    # Activity logs (who did what operations)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # create default admin if not exists
    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        admin_pass = generate_password_hash("admin123")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", admin_pass, "admin"),
        )
        conn.commit()

    conn.close()


# Initialize DB
if not os.path.exists(DB_NAME):
    init_db()
else:
    init_db()


# ---------- AUTH HELPERS ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "error")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def add_log(user_id, action):
    if not user_id:
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()


# ---------- ROUTES: AUTH ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Logged in as {user['username']} ({user['role']})", "success")
            add_log(user["id"], "Logged in")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    user_id = session.get("user_id")
    add_log(user_id, "Logged out")
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# (Optional) simple user registration for faculty (admin can create)
@app.route("/create-user", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        role = request.form.get("role", "faculty")

        if not username or not password:
            flash("Username and password required.", "error")
            return redirect(url_for("create_user"))

        conn = get_db()
        cur = conn.cursor()
        try:
            pw_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, pw_hash, role),
            )
            conn.commit()
            flash("User created successfully.", "success")
            add_log(session.get("user_id"), f"Created user {username} ({role})")
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
        finally:
            conn.close()

    return render_template("create_user.html")


# ---------- ROUTES: CORE PAGES ----------

@app.route("/")
@login_required
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM subjects")
    subjects_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM questions")
    questions_count = cur.fetchone()["c"]
    conn.close()
    return render_template(
        "index.html",
        subjects_count=subjects_count,
        questions_count=questions_count,
    )


# ---- SUBJECTS ----

@app.route("/subjects", methods=["GET", "POST"])
@admin_required
def subjects():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            code = request.form["code"].strip()
            name = request.form["name"].strip()
            if code and name:
                cur.execute(
                    "INSERT INTO subjects (code, name) VALUES (?, ?)", (code, name)
                )
                conn.commit()
                flash("Subject added.", "success")
                add_log(session.get("user_id"), f"Added subject {code} - {name}")

        elif action == "edit":
            subject_id = request.form["subject_id"]
            code = request.form["code"].strip()
            name = request.form["name"].strip()
            cur.execute(
                "UPDATE subjects SET code=?, name=? WHERE id=?",
                (code, name, subject_id),
            )
            conn.commit()
            flash("Subject updated.", "success")
            add_log(session.get("user_id"), f"Edited subject ID {subject_id}")

        elif action == "delete":
            subject_id = request.form["subject_id"]
            cur.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
            conn.commit()
            flash("Subject deleted.", "success")
            add_log(session.get("user_id"), f"Deleted subject ID {subject_id}")

    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()
    conn.close()
    return render_template("subjects.html", subjects=subjects_list)


# ---- MODULES / UNITS ----

@app.route("/subjects/<int:subject_id>/modules", methods=["GET", "POST"])
@admin_required
def modules(subject_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
    subject = cur.fetchone()

    if not subject:
        conn.close()
        flash("Subject not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            module_no = request.form["module_no"]
            title = request.form["title"].strip()
            if module_no and title:
                cur.execute(
                    "INSERT INTO modules (subject_id, module_no, title) VALUES (?, ?, ?)",
                    (subject_id, module_no, title),
                )
                conn.commit()
                flash("Module added.", "success")
                add_log(session.get("user_id"),
                        f"Added module {module_no} - {title} in subject {subject['code']}")

        elif action == "edit":
            module_id = request.form["module_id"]
            module_no = request.form["module_no"]
            title = request.form["title"].strip()
            cur.execute(
                "UPDATE modules SET module_no=?, title=? WHERE id=?",
                (module_no, title, module_id),
            )
            conn.commit()
            flash("Module updated.", "success")
            add_log(session.get("user_id"), f"Edited module ID {module_id}")

        elif action == "delete":
            module_id = request.form["module_id"]
            cur.execute("DELETE FROM modules WHERE id=?", (module_id,))
            conn.commit()
            flash("Module deleted.", "success")
            add_log(session.get("user_id"), f"Deleted module ID {module_id}")

    cur.execute(
        "SELECT * FROM modules WHERE subject_id=? ORDER BY module_no", (subject_id,)
    )
    modules_list = cur.fetchall()
    conn.close()

    return render_template("modules.html", subject=subject, modules=modules_list)


# ---- TOPICS ----

@app.route("/modules/<int:module_id>/topics", methods=["GET", "POST"])
@admin_required
def topics(module_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT m.*, s.name AS subject_name, s.code AS subject_code "
        "FROM modules m JOIN subjects s ON m.subject_id = s.id WHERE m.id=?",
        (module_id,),
    )
    module = cur.fetchone()

    if not module:
        conn.close()
        flash("Module not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name = request.form["name"].strip()
            if name:
                cur.execute(
                    "INSERT INTO topics (module_id, name) VALUES (?, ?)",
                    (module_id, name),
                )
                conn.commit()
                flash("Topic added.", "success")
                add_log(session.get("user_id"),
                        f"Added topic '{name}' in module {module['module_no']}")

        elif action == "edit":
            topic_id = request.form["topic_id"]
            name = request.form["name"].strip()
            cur.execute("UPDATE topics SET name=? WHERE id=?", (name, topic_id))
            conn.commit()
            flash("Topic updated.", "success")
            add_log(session.get("user_id"), f"Edited topic ID {topic_id}")

        elif action == "delete":
            topic_id = request.form["topic_id"]
            cur.execute("DELETE FROM topics WHERE id=?", (topic_id,))
            conn.commit()
            flash("Topic deleted.", "success")
            add_log(session.get("user_id"), f"Deleted topic ID {topic_id}")

    cur.execute("SELECT * FROM topics WHERE module_id=? ORDER BY id", (module_id,))
    topics_list = cur.fetchall()
    conn.close()
    return render_template("topics.html", module=module, topics=topics_list)


# ---- ANALYTICS (for Chart.js) ----

@app.route("/analytics")
@admin_required
def analytics():
    conn = get_db()
    cur = conn.cursor()

    # Questions count by difficulty
    cur.execute("SELECT difficulty, COUNT(*) AS c FROM questions GROUP BY difficulty")
    difficulty = {row["difficulty"]: row["c"] for row in cur.fetchall()}

    # Questions count by modules
    cur.execute("""
        SELECT m.module_no, COUNT(q.id) AS c
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        GROUP BY m.module_no
        ORDER BY m.module_no
    """)
    module_data = [(row["module_no"], row["c"]) for row in cur.fetchall()]

    conn.close()

    return render_template(
        "analytics.html",
        difficulty=difficulty,
        module_labels=[m[0] for m in module_data],
        module_values=[m[1] for m in module_data]
    )


# ---- EXPORT EXCEL ----

@app.route("/export-excel")
@admin_required
def export_excel():
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT q.id, q.question_text, q.marks, q.difficulty, q.cognitive_level,
               q.co, q.po, t.name AS topic, m.module_no, s.code AS subject
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
    """, conn)
    conn.close()

    file_path = "questionbank_export.xlsx"
    df.to_excel(file_path, index=False)
    add_log(session.get("user_id"), "Exported question bank to Excel")

    return send_file(file_path, as_attachment=True)


# ---- IMPORT EXCEL ----

@app.route("/import-excel", methods=["GET", "POST"])
@admin_required
def import_excel():
    if request.method == "POST":
        file = request.files["file"]
        if not file:
            flash("Please select a file.", "error")
            return redirect(url_for("import_excel"))

        df = pd.read_excel(file)

        conn = get_db()
        cur = conn.cursor()

        for _, row in df.iterrows():
            qt = str(row.get("question_text", "")).strip()
            if not qt:
                continue

            # Basic duplicate skip
            cur.execute("SELECT id FROM questions WHERE question_text=?", (qt,))
            if cur.fetchone():
                continue

            marks = int(row.get("marks", 2))
            difficulty = str(row.get("difficulty", "Medium"))
            cognitive = str(row.get("cognitive_level", "Understand"))
            co = str(row.get("co", "")).strip()
            po = str(row.get("po", "")).strip()

            cur.execute("""
                INSERT INTO questions (topic_id, question_text, marks, difficulty, cognitive_level, co, po)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (1, qt, marks, difficulty, cognitive, co, po))  # default topic_id=1 or adjust logic

        conn.commit()
        conn.close()
        flash("Questions imported successfully from Excel!", "success")
        add_log(session.get("user_id"), "Imported questions from Excel")
        return redirect(url_for("index"))

    return render_template("import_excel.html")


# ---- QUESTIONS ----

@app.route("/topics/<int:topic_id>/questions", methods=["GET", "POST"])
@login_required
def questions(topic_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT t.*, m.module_no, m.title AS module_title,
               s.code AS subject_code, s.name AS subject_name
        FROM topics t
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE t.id=?
    """,
        (topic_id,),
    )
    topic = cur.fetchone()

    if not topic:
        conn.close()
        flash("Topic not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        action = request.form.get("action")
        user_id = session.get("user_id")

        if action == "add":
            question_text = request.form["question_text"].strip()
            marks = request.form.get("marks", 2)
            difficulty = request.form.get("difficulty", "Medium")
            cognitive_level = request.form.get("cognitive_level", "Understand")
            co = request.form.get("co", "").strip()
            po = request.form.get("po", "").strip()

            if question_text:
                # DUPLICATE CHECK
                cur.execute(
                    "SELECT id FROM questions WHERE question_text=? AND topic_id=?",
                    (question_text, topic_id)
                )
                if cur.fetchone():
                    flash("Duplicate question found! Please add a different question.", "error")
                else:
                    cur.execute(
                        """
                        INSERT INTO questions (topic_id, question_text, marks, difficulty,
                                               cognitive_level, co, po, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            topic_id,
                            question_text,
                            marks,
                            difficulty,
                            cognitive_level,
                            co,
                            po,
                            user_id,
                        ),
                    )
                    conn.commit()
                    flash("Question added.", "success")
                    add_log(user_id, f"Added question in topic {topic_id}")

        elif action == "delete":
            q_id = request.form["question_id"]
            # Admin can delete any; faculty can delete only own questions
            if session.get("role") == "admin":
                cur.execute("DELETE FROM questions WHERE id=?", (q_id,))
            else:
                cur.execute(
                    "DELETE FROM questions WHERE id=? AND created_by=?",
                    (q_id, user_id),
                )
            conn.commit()
            flash("Question deleted (if you had permission).", "success")
            add_log(user_id, f"Deleted question ID {q_id}")

    cur.execute(
        "SELECT q.*, u.username as author FROM questions q "
        "LEFT JOIN users u ON q.created_by = u.id "
        "WHERE q.topic_id=? ORDER BY q.id DESC",
        (topic_id,),
    )
    questions_list = cur.fetchall()
    conn.close()

    return render_template("questions.html", topic=topic, questions=questions_list)


@app.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
@login_required
def edit_question(question_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT q.*, t.name AS topic_name, t.id AS topic_id,
               m.module_no, m.title AS module_title,
               s.code AS subject_code, s.name AS subject_name
        FROM questions q
        JOIN topics t ON q.topic_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN subjects s ON m.subject_id = s.id
        WHERE q.id=?
    """,
        (question_id,),
    )
    question = cur.fetchone()

    if not question:
        conn.close()
        flash("Question not found.", "error")
        return redirect(url_for("subjects"))

    user_id = session.get("user_id")
    role = session.get("role")

    # Only admin or creator can edit
    if role != "admin" and question["created_by"] != user_id:
        conn.close()
        flash("You do not have permission to edit this question.", "error")
        return redirect(url_for("questions", topic_id=question["topic_id"]))

    if request.method == "POST":
        question_text = request.form["question_text"].strip()
        marks = request.form.get("marks", 2)
        difficulty = request.form.get("difficulty", "Medium")
        cognitive_level = request.form.get("cognitive_level", "Understand")
        co = request.form.get("co", "").strip()
        po = request.form.get("po", "").strip()

        cur.execute(
            """
            UPDATE questions
            SET question_text=?, marks=?, difficulty=?,
                cognitive_level=?, co=?, po=?
            WHERE id=?
        """,
            (
                question_text,
                marks,
                difficulty,
                cognitive_level,
                co,
                po,
                question_id,
            ),
        )
        conn.commit()
        conn.close()
        flash("Question updated.", "success")
        add_log(user_id, f"Edited question ID {question_id}")
        return redirect(url_for("questions", topic_id=question["topic_id"]))

    conn.close()
    return render_template("edit_question.html", question=question)


# ---- SEARCH ----

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()

    results = []
    selected_subject = None
    selected_module = None
    selected_difficulty = None

    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        module_no = request.form.get("module_no")
        difficulty = request.form.get("difficulty")

        selected_difficulty = difficulty

        query = """
            SELECT q.*, t.name AS topic_name, m.module_no, m.title AS module_title,
                   s.code AS subject_code
            FROM questions q
            JOIN topics t ON q.topic_id = t.id
            JOIN modules m ON t.module_id = m.id
            JOIN subjects s ON m.subject_id = s.id
            WHERE 1=1
        """
        params = []

        if subject_id and subject_id != "all":
            query += " AND s.id = ?"
            params.append(subject_id)
            cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
            selected_subject = cur.fetchone()

        if module_no:
            query += " AND m.module_no = ?"
            params.append(module_no)
            selected_module = module_no

        if difficulty and difficulty != "all":
            query += " AND q.difficulty = ?"
            params.append(difficulty)

        query += " ORDER BY s.code, m.module_no, t.name"
        cur.execute(query, tuple(params))
        results = cur.fetchall()

    conn.close()
    return render_template(
        "search.html",
        subjects=subjects_list,
        results=results,
        selected_subject=selected_subject,
        selected_module=selected_module,
        selected_difficulty=selected_difficulty,
    )


# ---- QUESTION PAPER GENERATION ----

def generate_question_set(subject_id, total_questions, difficulty_distribution):
    conn = get_db()
    cur = conn.cursor()

    paper_questions = []

    for diff, count in difficulty_distribution.items():
        if count <= 0:
            continue
        cur.execute(
            """
            SELECT q.*, t.name AS topic_name, m.module_no, s.code AS subject_code
            FROM questions q
            JOIN topics t ON q.topic_id = t.id
            JOIN modules m ON t.module_id = m.id
            JOIN subjects s ON m.subject_id = s.id
            WHERE s.id = ? AND q.difficulty = ?
        """,
            (subject_id, diff),
        )
        rows = cur.fetchall()
        rows = list(rows)
        random.shuffle(rows)
        paper_questions.extend(rows[:count])

    conn.close()
    return paper_questions


def render_pdf_from_template(template_name, **context):
    html = render_template(template_name, **context)
    pdf_io = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_io)
    if pisa_status.err:
        return None
    pdf_io.seek(0)
    return pdf_io


@app.route("/generate-paper", methods=["GET", "POST"])
@login_required
def generate_paper():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subjects ORDER BY code")
    subjects_list = cur.fetchall()
    conn.close()

    if request.method == "POST":
        subject_id = int(request.form["subject_id"])
        exam_type = request.form.get("exam_type", "Internal")

        easy_q = int(request.form.get("easy_q", 2))
        med_q = int(request.form.get("med_q", 3))
        hard_q = int(request.form.get("hard_q", 1))

        total_q = easy_q + med_q + hard_q

        paper_questions = generate_question_set(
            subject_id,
            total_q,
            {"Easy": easy_q, "Medium": med_q, "Hard": hard_q},
        )

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
        subject = cur.fetchone()
        conn.close()

        pdf_io = render_pdf_from_template(
            "paper_template.html",
            subject=subject,
            exam_type=exam_type,
            questions=paper_questions,
        )

        if pdf_io is None:
            return "Error generating PDF", 500

        response = make_response(pdf_io.read())
        response.headers["Content-Type"] = "application/pdf"
        response.headers[
            "Content-Disposition"
        ] = f"attachment; filename=question_paper_{subject['code']}.pdf"
        return response

    return render_template("generate_paper.html", subjects=subjects_list)


# ---- LOGS VIEW ----

@app.route("/logs")
@admin_required
def logs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.action, l.timestamp, u.username
        FROM logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC
    """)
    data = cur.fetchall()
    conn.close()
    return render_template("logs.html", logs=data)



if __name__ == "__main__":
    app.run(debug=True)
