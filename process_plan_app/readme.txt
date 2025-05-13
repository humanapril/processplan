###create user table

CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(10) DEFAULT 'pending',  -- 'user', 'admin', or 'pending'
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


#### update users request 
UPDATE public.users
	SET role='admin', is_approved=true
	WHERE first_name = 'April';

####Create table for process plan 

CREATE TABLE process_plan_history (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    uploaded_filename VARCHAR(255) NOT NULL,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_code VARCHAR(20),
    response_summary TEXT,
    json_blob BYTEA
);