# 📦 Process Plan History App

A Flask-based web application for converting, uploading, storing, and reviewing process plan JSON files.
It includes user authentication, admin approval, and a history log of uploaded plans.

---

## 🚀 Features

- User registration and login with hashed passwords
- Admin approval system for new users
- Upload .xlsx process plans to auto convert to JSON process plans
- Upload JSON process plans and store metadata
- View upload history in a searchable, sortable table
- PostgreSQL backend
- Easily deployable on a remote server with Gunicorn + Nginx

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, Flask, SQLAlchemy
- **Frontend:** HTML, CSS, JavaScript (or Flask templates)
- **Database:** PostgreSQL
- **Deployment:** Gunicorn + Nginx (recommended), or Flask dev server

---

## 📂 Project Structure

For PostgresDB

###Create users Table

CREATE TABLE public.users (
id SERIAL PRIMARY KEY,
email VARCHAR(255) UNIQUE NOT NULL,
password_hash TEXT NOT NULL,
first_name VARCHAR(100),
last_name VARCHAR(100),
role VARCHAR(10) DEFAULT 'pending', -- 'user', 'admin', or 'pending'
is_approved BOOLEAN DEFAULT FALSE,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

#### Approve and Promote a User

UPDATE public.users
SET role = 'admin', is_approved = true
WHERE first_name = 'April';

#### Create process_plan_history Table

CREATE TABLE process_plan_history (
id SERIAL PRIMARY KEY,
user_email VARCHAR(255) NOT NULL,
uploaded_filename VARCHAR(255) NOT NULL,
upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
status_code VARCHAR(20),
response_summary TEXT,
json_blob BYTEA
);
