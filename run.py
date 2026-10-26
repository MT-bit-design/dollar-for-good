"""Start the app: python run.py  ->  http://127.0.0.1:8000"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Dollar for Good is running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")
