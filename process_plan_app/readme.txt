###
create user table

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
###


UPDATE public.users
	SET role='admin', is_approved=true
	WHERE first_name = 'April';


