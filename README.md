# School Attendance Management System

A web-based school attendance and management system built with Django, tailored for schools with daily attendance marking, automated SMS notifications to guardians/teachers, teacher attendance tracking, and Excel import/export capabilities.

Designed and optimized for production deployment on **Render** using **Supabase PostgreSQL** and **WhiteNoise** for static asset delivery.

---

## Features

- **Dashboard**: Role-based access for teachers and administrators with live attendance statistics.
- **Student Attendance**: Quick daily class attendance marking with instant SMS alert dispatch for absentees.
- **Teacher Attendance**: Daily teacher attendance marking with optional SMS notifications and monthly export.
- **Excel Bulk Import/Export**: Upload class rosters via `.xlsx` and export attendance logs directly to formatted Excel spreadsheets.
- **Security & Multi-Tenant**: Safe password management, CSRF protection, role restrictions, and environment-driven configuration.
- **Production Ready**: Configured for Render and Supabase with Gunicorn, WhiteNoise, connection pooling, and health checks.

---

## 1. Local Development Setup

### Prerequisites
- Python 3.11+
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd School-attendance
   ```

2. **Create and activate a Python virtual environment:**
   ```bash
   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1

   # Windows (Command Prompt)
   .venv\Scripts\activate.bat
   ```

3. **Install dependencies inside the virtual environment:**
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```

   Configure `.env` for local development:
   ```env
   SECRET_KEY=django-insecure-local-dev-key-change-in-production
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
   # Leave DATABASE_URL blank to automatically use local SQLite (db.sqlite3)
   # DATABASE_URL=
   SMS_TOKEN=
   SCHOOL_SHORT_NAME=Shaheed Nur Hossain Memorial School
   SCHOOL_FULL_NAME=Shaheed Nur Hossain Memorial School, Biral, Dinajpur
   ```

5. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser (admin account):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server:**
   ```bash
   python manage.py runserver
   ```
   Open your browser at `http://127.0.0.1:8000/`.

---

## 2. Supabase PostgreSQL Setup

1. Sign in to [Supabase](https://supabase.com) and create a new project.
2. Go to **Project Settings** > **Database**.
3. Under **Connection string**, select **URI**.
4. Choose either:
   - **Direct Connection** (Port `5432`): Best for migrations and standard connections.
     ```text
     postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres?sslmode=require
     ```
   - **Session Pooler** (Port `5432`): Recommended for cloud environments with dynamic IPs (like Render Free).
     ```text
     postgresql://postgres.[YOUR-PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require
     ```
5. Set this connection string as the `DATABASE_URL` environment variable in your local `.env` (for testing) and on Render.

---

## 3. SQLite → Supabase PostgreSQL Data Migration

If you have existing data in `db.sqlite3` (students, teachers, past attendance records) and want to transfer it to Supabase PostgreSQL, follow this safe, native workflow:

### Step 1: Export data from SQLite
With your `.venv` activated and `DATABASE_URL` commented out (or pointed to SQLite):
```bash
python manage.py dumpdata --natural-foreign --natural-primary --exclude auth.permission --exclude contenttypes --indent 2 > data.json
```
*(Excluding `auth.permission` and `contenttypes` prevents primary key collisions on the new database).*

### Step 2: Apply schema to Supabase PostgreSQL
Set `DATABASE_URL` in your `.env` to your Supabase PostgreSQL connection string, then run:
```bash
python manage.py migrate
```

### Step 3: Import data into PostgreSQL
Load the exported data:
```bash
python manage.py loaddata data.json
```

### Step 4: Verify
Run Django tests or check the admin panel to confirm all records migrated successfully:
```bash
python manage.py test
```

> **Note:** Never commit `data.json` containing sensitive school or user information to public Git repositories.

---

## 4. Render Deployment Guide

### Option A: Standard Render Web Service (Recommended)

1. Push your repository to your GitHub account.
2. Log in to [Render](https://render.com) and click **New +** > **Web Service**.
3. Select your GitHub repository.
4. Fill in the service details:
   - **Name**: `school-attendance` (or your preferred name)
   - **Region**: Choose the region closest to Bangladesh (e.g., Singapore)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     ./build.sh
     ```
   - **Start Command**:
     ```bash
     gunicorn core.wsgi:application
     ```
5. Add the following **Environment Variables** in the Render Dashboard:

| Variable | Value / Description |
| :--- | :--- |
| `PYTHON_VERSION` | `3.11.10` |
| `DEBUG` | `False` |
| `SECRET_KEY` | Generate a strong, random 50+ character string |
| `DATABASE_URL` | Your Supabase connection URI with `?sslmode=require` |
| `ALLOWED_HOSTS` | Optional custom domains (e.g. `yourdomain.com`). Render hostname is auto-detected. |
| `CSRF_TRUSTED_ORIGINS` | Optional custom HTTPS domains (e.g. `https://yourdomain.com`). |
| `SMS_TOKEN` | Your `bdbulksms` API token |
| `SCHOOL_SHORT_NAME` | `Shaheed Nur Hossain Memorial School` |
| `SCHOOL_FULL_NAME` | `Shaheed Nur Hossain Memorial School, Biral, Dinajpur` |

6. Click **Deploy Web Service**.
7. Create your initial admin user on Render by opening the **Shell** tab in the Render dashboard:
   ```bash
   python manage.py createsuperuser
   ```

### Option B: Render Blueprint (`render.yaml`)

This repository includes a `render.yaml` specification. You can deploy using **Blueprints** on Render:
1. Go to **Blueprints** on Render and connect this repository.
2. Render will automatically configure the build and start commands and generate a secure `SECRET_KEY`.
3. Provide the `DATABASE_URL` and `SMS_TOKEN` when prompted in the dashboard.

---

## 5. Health Check Endpoint

A lightweight health check endpoint is available at:
```text
GET /health/
```
Response:
```json
{
  "status": "ok"
}
```
This endpoint executes no database queries and makes no external calls, making it ideal for Render liveness probes or external uptime monitoring.

---

## 6. Automated Testing

Run the automated test suite locally at any time:
```bash
source .venv/bin/activate
python manage.py test
```

Run Django system validation:
```bash
python manage.py check
```
