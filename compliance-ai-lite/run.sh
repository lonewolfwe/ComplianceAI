#!/bin/bash
# Shell script to run the ComplianceAI Lite FastAPI server

# Activate virtual environment and run the app
./.venv/Scripts/python.exe -m uvicorn app:app --reload
