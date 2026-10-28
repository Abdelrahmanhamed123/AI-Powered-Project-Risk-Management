# AI-Powered Project Risk Management System (APPRM)

## 📌 Project Overview
The AI-Powered Project Risk Management System is an advanced software engineering project designed to automate project tracking, analyze task dependencies, predict task delays using machine learning models, and generate intelligent risk mitigation recommendations and simulations.

## 👥 Team Members & Service Ownership
* **Abdelrahman Hamed** (`access-service`): Authentication, Roles, Permissions, and Activity Logs.
* **Mohamed Sedeek** (`project-service`): Projects, Milestones, Tasks, and Deadlines.
* **Omar Abdou** (`dependency-service`): Task Dependencies, Workload, and Critical Path.
* **Mazen Essam** (`risk-ai`): AI Delay Prediction, Risk Assessment, Explanations, and Model Evaluation.
* **Loay Mohamed** (`reports`): Recommendations, What-if Simulations, Anomaly Detection, Dashboards, and Reports.

## 🗂️ Jira Project Board
You can track our agile progress, sprints, user stories, and burn-down charts via our Jira Board:
* **https://abdelrahman-tem.atlassian.net/jira/software/projects/APPRM/boards/3/backlog?atlOrigin=eyJpIjoiNTY1NzI1M2Y3Y2Y3NGRkZWJkODM0NmExOWM4NDFlN2QiLCJwIjoiaiJ9**

## 🛠️ Tech Stack
* **Backend:** Python, FastAPI
* **Frontend / UI:** React / Dashboards
* **Database & Storage:** MongoDB Atlas / PostgreSQL
* **Automation & Testing:** Playwright, Pytest

## 📂 Monorepo Folder Structure
```text
APPRM-System/
│
├── access-service/       # Authentication, RBAC, and Audit logs
├── project-service/      # Projects, Milestones, and Tasks management
├── dependency-service/   # Task dependencies, workload, and critical path
├── risk-ai/              # ML models, delay predictions, and risk assessment
├── reports-service/      # Recommendations, simulations, alerts, and dashboards
└── README.md
