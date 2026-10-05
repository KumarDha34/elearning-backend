# E-Learning Platform for Nepal - Backend API

Production-ready backend API for a Nepal-focused E-Learning platform. Built with Django REST Framework to serve web and mobile clients.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [User Roles](#user-roles)
- [Content Workflow](#content-workflow)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security](#security)
- [Team](#team)
- [License](#license)

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

---

## 👥 User Roles

| Role | Responsibilities |
|------|------------------|
| **Student** | View notes, view old questions, take quizzes (future) |
| **Teacher** | Upload notes, upload old questions, view own content |
| **Editor** | Review, approve, reject submitted content |
| **Admin** | Full platform control, user management, analytics |



---
# E-Learning Platform for Nepal - Backend API

Production-ready backend API for a Nepal-focused E-Learning platform, built with Django REST Framework. Serves web and mobile clients with role-based access control.

---

## Features

- Phone-based authentication with OTP verification
- JWT authentication (access + refresh tokens)
- Role-based access control (Student, Teacher, Editor, Admin)
- Notes management with CKEditor 5
- Old question papers (SEE, NEB, and other exams)
- Content approval workflow (Draft → Pending → Published/Rejected)
- Academic taxonomy (Schools, Faculties, Class Levels, Subjects, Chapters)
- User profiles (Student and Teacher with verification)
- Swagger/OpenAPI documentation

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | Django 5.0 + Django REST Framework |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Async Tasks | Celery + Celery Beat |
| Auth | SimpleJWT + OTP |
| Rich Text | CKEditor 5 |
| API Docs | drf-spectacular (Swagger) |
| Container | Docker |

---

## Setup Instructions

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Clone repository
git clone https://github.com/KumarDha34/elearning-backend.git
cd elearning-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Setup database
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

---

## API Documentation

Interactive API documentation is available when the server is running:

| URL | Description |
|-----|-------------|
| `/api/v1/docs/` | Swagger UI |
| `/api/v1/schema/` | OpenAPI Schema |

**Base URL:** `http://127.0.0.1:8000/api/v1/`

**Authentication:** All protected endpoints require a Bearer token in the header:
```
Authorization: Bearer <access_token>
```

---

### Authentication APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/auth/signup/` | Register with name, phone, and role | Public |
| POST | `/auth/otp/send/` | Send OTP to a phone number | Public |
| POST | `/auth/otp/verify/` | Verify OTP and activate account | Public |
| POST | `/auth/login/` | Login with phone and password | Public |
| POST | `/auth/logout/` | Logout and blacklist refresh token | Authenticated |
| POST | `/auth/token/refresh/` | Refresh access token | Public |
| GET | `/auth/me/` | Get current user info | Authenticated |
| POST | `/auth/password/reset/` | Request password reset or change password | Public/Authenticated |
| POST | `/auth/password/reset/confirm/` | Confirm password reset with OTP | Public |

---

### Profile APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/auth/profile/student/complete/` | Complete student profile | Authenticated |
| POST | `/auth/profile/teacher/complete/` | Complete teacher profile | Authenticated |
| PATCH | `/auth/profile/student/update/` | Update student profile | Student |
| PATCH | `/auth/profile/teacher/update/` | Update teacher profile | Teacher |

---

### Academic APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/academics/schools/` | List all schools | Authenticated |
| POST | `/academics/schools/` | Create school | Admin |
| GET | `/academics/schools/{id}/` | Get school details | Authenticated |
| PATCH | `/academics/schools/{id}/` | Update school | Admin/Creator |
| POST | `/academics/schools/{id}/verify/` | Verify school | Admin |
| GET | `/academics/schools/my_schools/` | Get own created schools | Authenticated |
| GET | `/academics/faculties/` | List faculties | Authenticated |
| POST | `/academics/faculties/` | Create faculty | Admin |
| GET | `/academics/faculties/{id}/` | Get faculty details | Authenticated |
| PATCH | `/academics/faculties/{id}/` | Update faculty | Admin |
| GET | `/academics/class-levels/` | List class levels | Authenticated |
| POST | `/academics/class-levels/` | Create class level | Admin |
| GET | `/academics/class-levels/{id}/` | Get class level details | Authenticated |
| PATCH | `/academics/class-levels/{id}/` | Update class level | Admin |
| GET | `/academics/subjects/` | List subjects | Authenticated |
| POST | `/academics/subjects/` | Create subject | Admin |
| GET | `/academics/subjects/{id}/` | Get subject details | Authenticated |
| PATCH | `/academics/subjects/{id}/` | Update subject | Admin |
| GET | `/academics/chapters/` | List chapters | Authenticated |
| POST | `/academics/chapters/` | Create chapter | Admin |
| GET | `/academics/chapters/{id}/` | Get chapter details | Authenticated |
| PATCH | `/academics/chapters/{id}/` | Update chapter | Admin |
| DELETE | `/academics/chapters/{id}/` | Delete chapter | Admin |
| GET | `/academics/teacher-schools/` | List teacher-school affiliations | Authenticated |
| GET | `/academics/teacher-schools/my_schools/` | Get own schools | Teacher |

---

### Notes APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/notes/` | List published notes | Authenticated |
| POST | `/notes/create/` | Upload a note | Verified Teacher/Admin |
| POST | `/notes/preview/` | Preview note content | Verified Teacher/Admin |
| GET | `/notes/{id}/` | Get note details | Authenticated |
| PATCH | `/notes/{id}/update/` | Update note | Owner/Admin |
| DELETE | `/notes/{id}/delete/` | Delete note | Owner/Admin |
| PATCH | `/notes/{id}/status/` | Update note status | Owner/Admin |
| POST | `/notes/{id}/approve/` | Approve/reject note | Editor/Admin |
| POST | `/notes/{id}/resubmit/` | Resubmit rejected note | Owner/Admin |
| GET | `/notes/{id}/reject-info/` | Get rejection details | Owner/Editor/Admin |

---

### Old Questions APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/notes/old-questions/` | List published old questions | Authenticated |
| POST | `/notes/old-questions/create/` | Upload old question paper | Verified Teacher/Admin |
| GET | `/notes/old-questions/{id}/` | Get question details | Authenticated |
| PATCH | `/notes/old-questions/{id}/update/` | Update question | Owner/Admin |
| DELETE | `/notes/old-questions/{id}/delete/` | Delete question | Owner/Admin |
| POST | `/notes/old-questions/{id}/approve/` | Approve/reject question | Admin |
| POST | `/notes/old-questions/{id}/resubmit/` | Resubmit rejected question | Owner/Admin |
| GET | `/notes/old-questions/{id}/reject-info/` | Get rejection details | Owner/Admin |
| GET | `/notes/old-questions/my-questions/` | List own questions | Teacher |

---

### Admin APIs

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/auth/admin/users/` | List all users | Admin |
| POST | `/auth/admin/users/create/` | Create editor user | Admin |
| PATCH | `/auth/admin/users/{phone_number}/` | Update user role or status | Admin |
| PATCH | `/auth/admin/teachers/{phone_number}/verify/` | Verify or unverify teacher | Admin |

