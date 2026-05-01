import subprocess
import time
import webbrowser
import os

def open_window(title, command):
    subprocess.Popen([
        'cmd', '/K',
        f'title {title} && {command}'
    ], creationflags=subprocess.CREATE_NEW_CONSOLE)

def main():
    print(f"\n[1/7] Starting Docker containers...")
    result = subprocess.run(
        ['docker', 'start', 'news_system_postgres', 'news_system_redis'],
        capture_output=True, text=True
    )
    print(f"Docker: {result.stdout.strip() or result.stderr.strip()}")
    time.sleep(3)

    print(f"[2/7] Starting Ollama...")
    open_window("Ollama", "ollama serve")
    time.sleep(4)

    print(f"[3/7] Starting Flask API...")
    open_window("Flask API - Port 5000", "cd /d D:\\PROJECTS\\NA && python api/api.py")
    time.sleep(3)

    print(f"[4/7] Starting Celery Worker...")
    open_window("Celery Worker", "cd /d D:\\PROJECTS\\NA && celery -A celery_app worker --loglevel=info -P solo")
    time.sleep(2)

    print(f"[5/7] Starting Celery Beat...")
    open_window("Celery Beat", "cd /d D:\\PROJECTS\\NA && celery -A celery_app beat --loglevel=info")
    time.sleep(2)

    print(f"[6/7] Starting React Frontend...")
    open_window("React Frontend - Port 5173", "cd /d D:\\PROJECTS\\NA\\news-weaver\\news-weaver-main && npm run dev")
    time.sleep(5)

    print(f"[7/7] Opening browser tabs...")
    webbrowser.open("http://localhost:5173")
    time.sleep(1)
    webbrowser.open("http://localhost:5000/api/health")

    print("\n" + "="*50)
    print("ALL SERVICES STARTED")
    print("="*50)
    print("React Dashboard : http://localhost:5173")
    print("Flask API       : http://localhost:5000")
    print("Flask Health    : http://localhost:5000/api/health")
    print("Streamlit       : http://localhost:8501 (if running)")
    print("="*50)
    print("\nClose this window or press Ctrl+C to stop monitoring.")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
