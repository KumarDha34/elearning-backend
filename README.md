# E-Learning Platform for Nepal - Backend API

Production-ready backend API for a Nepal-focused E-Learning platform. Built with Django REST Framework to serve web and mobile clients.
---

## 🎯 Overview

This backend powers a modern e-learning platform built specifically for Nepal's education system. It connects students, teachers, editors, and administrators through a secure, role-based API.

The platform enables:
- **Teachers** to share notes and old question papers
- **Editors** to review and approve content before publishing
- **Students** to access quality educational resources
- **Admins** to manage the entire platform

The API is designed to serve both a React web application and Flutter/React Native mobile applications.

---

## ✨ Features

### Authentication & Security
- Phone-based signup with OTP verification
- JWT authentication (access + refresh tokens)
- Forgot password and change password flows
- Role-based access control
- Token blacklisting on logout
- Login throttling

### User Management
- Student profiles with school/class/faculty
- Teacher profiles with verification workflow
- Multi-school teacher affiliation
- Profile image uploads
- Alternative contacts support

### Content Management
- Notes with CKEditor 5 rich text editor
- Old question papers (SEE, NEB, and other exams)
- Draft → Pending → Published/Rejected workflow
- Resubmission for rejected content
- View tracking and statistics

### Academic Taxonomy
- Schools / Colleges / Universities
- Faculties (Science, Management, etc.)
- Class levels (Grade 10, 11, 12)
- Subjects and chapters
- School verification system

### API & Documentation
- RESTful API design
- Swagger/OpenAPI documentation
- Consistent error responses
- Pagination on all list endpoints
- Search and filtering

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Framework** | Django 5.0 + Django REST Framework |
| **Database** | PostgreSQL 15 |
| **Cache** | Redis 7 |
| **Async Tasks** | Celery + Celery Beat |
| **Auth** | SimpleJWT + OTP |
| **Rich Text** | CKEditor 5 |
| **API Docs** | drf-spectacular (Swagger) |
| **File Handling** | Pillow |
| **Environment** | python-dotenv |
| **Testing** | pytest + pytest-django |
| **CI/CD** | GitHub Actions |
| **Container** | Docker + Docker Compose |
| **Monitoring** | Sentry (optional) |

---


---

## 📁 Project Structure

```
elearning-backend/
├── apps/
│   ├── accounts/              # Auth, profiles, OTP
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   └── services.py
│   │
│   ├── academics/             # Academic taxonomy
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   └── notes/                 # Notes & questions
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── permissions.py
│
├── config/                    # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── tests/
├── scripts/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── manage.py
```

---

## 🚀 Setup Instructions

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Git

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/KumarDha34/elearning-backend.git
cd elearning-backend
```

**2. Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials
```

**5. Setup database**
```bash
python manage.py migrate
```

**6. Create superuser**
```bash
python manage.py createsuperuser
```

**7. Run server**
```bash
python manage.py runserver
```

**8. Access API**
```
http://127.0.0.1:8000/api/v1/docs/
```

---


## 📖 API Documentation

Access interactive API documentation:

| URL | Description |
|-----|-------------|
| `/api/v1/docs/` | Swagger UI |
| `/api/v1/schema/` | OpenAPI Schema |

### Core Endpoints

| Module | Endpoint | Description |
|--------|----------|-------------|
| **Auth** | `/api/v1/auth/signup/` | User registration |
| | `/api/v1/auth/login/` | Login |
| | `/api/v1/auth/otp/send/` | Send OTP |
| | `/api/v1/auth/otp/verify/` | Verify OTP |
| | `/api/v1/auth/me/` | Current user |
| **Profiles** | `/api/v1/auth/profile/student/complete/` | Complete student profile |
| | `/api/v1/auth/profile/teacher/complete/` | Complete teacher profile |
| **Academics** | `/api/v1/academics/schools/` | List schools |
| | `/api/v1/academics/subjects/` | List subjects |
| **Notes** | `/api/v1/notes/` | List notes |
| | `/api/v1/notes/create/` | Upload note |
| | `/api/v1/notes/{id}/approve/` | Approve/reject |
| **Old Questions** | `/api/v1/notes/old-questions/` | List past papers |
| | `/api/v1/notes/old-questions/create/` | Upload paper |

