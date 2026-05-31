import subprocess
import time
import sys
import os
import webbrowser
import urllib.request

def wait_for_backend(url="http://127.0.0.1:8000/health", timeout=60):
    """Poll until the FastAPI backend is healthy or timeout."""
    print(f"⏳ Waiting for backend at {url} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    print("✅ Backend is ready!")
                    return True
        except Exception:
            time.sleep(1)
    print("⚠️  Backend did not respond within timeout — starting frontend anyway.")
    return False

def run_services():
    print("🚀 Starting Judicial AI Platform...")
    
    # 1. Start FastAPI Backend first
    print("Starting FastAPI Backend on http://localhost:8000...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=os.getcwd()
    )
    
    # 2. Wait for FastAPI to be healthy before starting Streamlit
    wait_for_backend()
    
    # 3. Start Streamlit Frontend
    print("Starting Streamlit Frontend on http://localhost:8501...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py",
         "--server.port", "8501",
         "--browser.gatherUsageStats", "false"],
        cwd=os.getcwd()
    )
    
    # 4. Open Dashboard in Browser
    time.sleep(3)
    print("Opening Dashboard at http://localhost:8501...")
    webbrowser.open("http://localhost:8501")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        backend_process.terminate()
        frontend_process.terminate()

if __name__ == "__main__":
    run_services()
