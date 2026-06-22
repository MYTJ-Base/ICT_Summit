# How to Run KnowMe

This guide will walk you through running the KnowMe backend server (the "Engine"). The server is built with FastAPI and runs on Python.

## 1. Prerequisites
Make sure you have Python 3.10+ installed. It is highly recommended to use the existing virtual environment.

## 2. Activate the Virtual Environment
From the root of the project directory (`/home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/`):
```bash
source .venv/bin/activate
```

## 3. Install Dependencies
If you haven't already, install the required packages (or sync with `uv` if applicable):
```bash
pip install -r scripts/requirements.txt
# Alternatively, if you use uv:
uv pip install -r scripts/requirements.txt
```

## 4. Run the Server
Use `uvicorn` to run the FastAPI application:
```bash
# Ensure the python path is set to the current directory
export PYTHONPATH=.

# Start the server
uvicorn src.main:app --host 127.0.0.1 --port 8085 --reload
```
You should see output indicating that the server is running. You can now access the API at `http://127.0.0.1:8085`. 

You can also view the interactive Swagger API documentation by navigating to `http://127.0.0.1:8085/docs` in your web browser.

## 5. Validating the Flow
If you want to validate that the backend is working through a demo flow (without using a frontend), you can run the validation script:
```bash
export PYTHONPATH=.
python scripts/validate_knowme.py
```
This script will:
1. Boot the server automatically.
2. Register a new user.
3. Start a diagnostic session and submit responses.
4. Create a knowledge base note and demonstrate the AI engine capability.
