# QBMS
question bank management system to generate a question bank
A web-based Question Bank Management System designed to help educational institutions efficiently create, manage, and analyze subject-wise question banks with CO–PO mapping, difficulty levels, and automatic question paper generation.

This system is ideal for internal and external examinations, ensuring structured assessment design and easy question retrieval.
Project Objectives

To maintain a centralized, unit-wise question bank

To map questions with Course Outcomes (CO) and Program Outcomes (PO)

To categorize questions based on difficulty and cognitive levels

To automate question paper generation

To provide role-based access for administrators and faculty
User Roles
🔹 Admin

Manage subjects, modules, topics

Create and manage faculty accounts

View analytics and reports

Import/export questions using Excel

Monitor activity logs

Generate question papers (PDF)

🔹 Faculty

Add, edit, and manage questions topic-wise

Assign difficulty, cognitive level, CO & PO

Search and reuse existing questions

Generate question papers

View subject-wise question lists
Key Features

.Subject → Module → Topic hierarchy

.Cognitive level tagging (Bloom’s Taxonomy)

.Difficulty classification (Easy / Medium / Hard)

.Advanced search & filters

.Auto-generated question papers (PDF)

.Admin analytics dashboard (Chart.js)

.Subject-wise question visualization

.Excel import & export

.Activity logging

.Secure login with role-based dashboards

.Responsive UI using Tailwind CSS

tech stack
| Layer          | Technology                     |
| -------------- | ------------------------------ |
| Frontend       | HTML, Tailwind CSS, JavaScript |
| Backend        | Python (Flask)                 |
| Database       | SQLite                         |
| Charts         | Chart.js                       |
| PDF Generation | xhtml2pdf                      |
| Authentication | Flask Sessions                 |
| File Handling  | Pandas (Excel import/export)   |

project structure
Question-Bank-Management-System/
│
├── app.py
├── question_bank.db
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── faculty_dashboard.html
│   ├── subjects.html
│   ├── modules.html
│   ├── topics.html
│   ├── questions.html
│   ├── analytics.html
│   └── ...
│
├── static/
│   ├── university_logo.png
│   └── university_bg.jpg
│
└── README.md

How to Run the Project

Clone the repository

git clone https://github.com/your-username/question-bank-management-system.git


Install dependencies

pip install flask pandas xhtml2pdf werkzeug


Run the application

python app.py


Open browser:

http://127.0.0.1:5000

Default Admin Credentials
Username: admin
Password: admin123

Use Cases

College internal examinations

End-semester assessments

Faculty question bank maintenance

CO–PO attainment analysis

Accreditation and audit preparation

Future Enhancements

Student portal

AI-based question difficulty prediction

Outcome attainment reports

Multi-department support

Cloud database integration
