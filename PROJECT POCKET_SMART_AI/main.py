"""
main.py - Entrypoint alias for PocketSmart AI application.
Allows running with either `uvicorn main:app` or `python main.py`.
"""

import os
import uvicorn
from app import app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting PocketSmart: AI Budget Planner on http://localhost:{port}...")
    uvicorn.run("main:app", host=host, port=port, reload=True)
