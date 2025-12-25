#!/usr/bin/env python3
"""
Script to create .env file from template
"""
import os

env_content = """# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ai_base_db

# Application Configuration
APP_NAME=FastBase AI
APP_VERSION=1.0.0
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Logging Configuration
LOG_LEVEL=INFO
"""

if __name__ == "__main__":
    if os.path.exists(".env"):
        print(".env file already exists. Skipping creation.")
    else:
        with open(".env", "w") as f:
            f.write(env_content)
        print(".env file created successfully!")
        print("Please update the OPENAI_API_KEY and MongoDB settings in .env file.")

