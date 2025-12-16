<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/6d32f58c-24a8-4b57-86fb-0ff5003b6399" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/54017872-bb0b-46cc-96ad-f5c48528352c" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/d59e6018-0344-446a-b9bc-06a31a804b8d" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/a3dae8a5-3632-48e4-be65-b272e4b7d1c5" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/b64f3d1c-2415-4aab-9caa-3f71a46ef1ea" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/f5b443db-df46-4389-ae43-4a91d9302407" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/3734c850-6095-433b-881a-d28095d140e2" />
<img width="1366" height="768" alt="image" src="https://github.com/user-attachments/assets/13448353-5fd7-4aff-8e3b-1a6cae980c7d" />


📘 Question Bank Management System (QBMS)

A **web-based Question Bank Management System** designed to help educational institutions efficiently create, manage, and analyze subject-wise question banks with **CO–PO mapping**, **difficulty levels**, and **automatic question paper generation**.

This system is ideal for **internal and external examinations**, ensuring structured assessment design and easy question retrieval.



🎯 Project Objectives

* To maintain a **centralized, unit-wise question bank**
* To map questions with **Course Outcomes (CO)** and **Program Outcomes (PO)**
* To categorize questions based on **difficulty and cognitive levels**
* To automate **question paper generation**
* To provide **role-based access** for administrators and faculty



👥 User Roles

🔹 Admin

* Manage subjects, modules, topics
* Create and manage faculty accounts
* View analytics and reports
* Import/export questions using Excel
* Monitor activity logs
* Generate question papers (PDF)

🔹 Faculty

* Add, edit, and manage questions topic-wise
* Assign difficulty, cognitive level, CO & PO
* Search and reuse existing questions
* Generate question papers
* View subject-wise question lists



⚙️ Key Features

* 📚 Subject → Module → Topic hierarchy
* 🧠 Cognitive level tagging (Bloom’s Taxonomy)
* 🎯 Difficulty classification (Easy / Medium / Hard)
* 🔍 Advanced search & filters
* 📄 Auto-generated question papers (PDF)
* 📊 Admin analytics dashboard (Chart.js)
* 📈 Subject-wise question visualization
* 📥 Excel import & export
* 🧾 Activity logging
* 🔐 Secure login with role-based dashboards
* 🎨 Responsive UI using Tailwind CSS



🛠️ Tech Stack

| Layer          | Technology                     |
| -------------- | ------------------------------ |
| Frontend       | HTML, Tailwind CSS, JavaScript |
| Backend        | Python (Flask)                 |
| Database       | SQLite                         |
| Charts         | Chart.js                       |
| PDF Generation | xhtml2pdf                      |
| Authentication | Flask Sessions                 |
| File Handling  | Pandas (Excel import/export)   |



📁 Project Structure


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




🚀 How to Run the Project

1. Clone the repository

   .bash
   git clone https://github.com/your-username/question-bank-management-system.git
   
2. Install dependencies

   .bash
   pip install flask pandas xhtml2pdf werkzeug
   
3. Run the application

   .bash
   python app.py
   
4. Open browser:

   
   http://127.0.0.1:5000
   

🔑 Default Admin Credentials


Username: admin
Password: admin123




📌 Use Cases

* College internal examinations
* End-semester assessments
* Faculty question bank maintenance
* CO–PO attainment analysis
* Accreditation and audit preparation



🌟 Future Enhancements

* Student portal
* AI-based question difficulty prediction
* Outcome attainment reports
* Multi-department support
* Cloud database integration



👨‍💻 Developed By

pathapati lakshmi supriya


