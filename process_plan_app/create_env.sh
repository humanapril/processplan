#!/bin/bash

# Navigate to your app directory
cd ~/processplan/process_plan_app || {
  echo "❌ Could not change directory to process_plan_app"
  exit 1
}

# Create the .env file with required variables
cat <<EOF > .env
# Database settings
DB_USER=figure
DB_PASSWORD=figure
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=process_plan_db

# Flask settings
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Make sure it's not tracked by git
echo ".env" >> .gitignore

echo "✅ .env file created successfully in $(pwd)"
