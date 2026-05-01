import sys
import socket
import importlib

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def print_result(label, success, fix_cmd=""):
    status = f"{GREEN}[OK]{RESET}" if success else f"{RED}[FAIL]{RESET}"
    print(f"{label:<40} {status}")
    if not success and fix_cmd:
        print(f"  FIX: {fix_cmd}")

def check_setup():
    # 1. Python Version Check
    py_ok = sys.version_info.major == 3 and sys.version_info.minor >= 11
    print_result("Python 3.11+", py_ok, "Download Python 3.11+ from https://www.python.org/downloads/")

    # 2. Package Imports Check
    # Map package names to their python import names
    packages = {
        "feedparser": "feedparser",
        "newspaper3k": "newspaper",
        "keybert": "keybert",
        "celery": "celery",
        "psycopg2": "psycopg2",
        "pillow": "PIL",
        "requests": "requests",
        "tweepy": "tweepy",
        "streamlit": "streamlit",
        "flask": "flask"
    }

    installed_requests = False
    installed_psycopg2 = False

    for pkg_name, import_name in packages.items():
        try:
            importlib.import_module(import_name)
            print_result(f"Package: {pkg_name}", True)
            if pkg_name == "requests": installed_requests = True
            if pkg_name == "psycopg2": installed_psycopg2 = True
        except ImportError:
            print_result(f"Package: {pkg_name}", False, f"pip install {pkg_name}")

    # 3. Ollama Check
    if installed_requests:
        import requests
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m.get('name', '') for m in resp.json().get('models', [])]
                if any("mistral" in m.lower() for m in models):
                    print_result("Ollama @ localhost:11434 (mistral)", True)
                else:
                    print_result("Ollama @ localhost:11434 (mistral)", False, "ollama pull mistral")
            else:
                print_result("Ollama @ localhost:11434 (mistral)", False, "Ensure Ollama is running")
        except:
            print_result("Ollama @ localhost:11434 (mistral)", False, "Check if Ollama is running at http://localhost:11434")
    else:
        print_result("Ollama (Check Skipped)", False, "Install 'requests' package first")

    # 4. PostgreSQL Check
    if installed_psycopg2:
        import psycopg2
        try:
            # Attempting connection with local defaults
            conn = psycopg2.connect(dbname="news_system", user="postgres", password="postgres", host="localhost", port=5434, connect_timeout=3)
            conn.close()
            print_result("PostgreSQL (news_system DB)", True)
        except Exception as e:
            error_msg = str(e).replace('\n', ' ')
            print_result("PostgreSQL (news_system DB)", False, f'psql -U postgres -c "CREATE DATABASE news_system;"')
    else:
        print_result("PostgreSQL (Check Skipped)", False, "Install 'psycopg2' package first")

    # 5. Redis Check
    try:
        with socket.create_connection(("localhost", 16380), timeout=2) as s:
            print_result("Redis @ localhost:16380", True)
    except:
        print_result("Redis @ localhost:16380", False, "docker run -d -p 16380:6379 redis (or start redis-server)")

if __name__ == "__main__":
    # Enable ANSI escape characters on Windows
    if sys.platform == "win32":
        import os
        os.system("")
    
    check_setup()
