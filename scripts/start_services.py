import os
import sys
import time
import subprocess
import requests
import webbrowser

def check_ollama():
    """Returns True if the Ollama API is responding on localhost:11434."""
    try:
        response = requests.get("http://localhost:11434/", timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def open_in_new_window(cmd_list):
    """
    Spawns a new Windows command prompt to run the given list.
    We prepend 'cmd /K' so the window stays open to show logs if it crashes,
    otherwise CREATE_NEW_CONSOLE alone will immediately close on exit.
    """
    full_cmd = ["cmd", "/K"] + cmd_list
    print(f"    -> Spawning new console for: {' '.join(cmd_list)}")
    # CREATE_NEW_CONSOLE creates a visible new command line window (Windows only feature)
    subprocess.Popen(full_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

def main():
    if os.name != "nt":
        print("This script is designed for Windows only.")
        sys.exit(1)

    print("========================================")
    print("      Autonomous News Services          ")
    print("========================================\n")

    # Step 1: Check and Start Ollama
    print("[1] Checking Ollama service at http://localhost:11434 ...")
    if not check_ollama():
        print("    -> Ollama is NOT running. Attempting to start...")
        open_in_new_window(["ollama", "serve"])
        # Give Ollama a moment to bind its port before continuing
        time.sleep(3)
        if check_ollama():
            print("    -> Ollama successfully started.")
        else:
            print("    -> [WARNING] Attempted to start Ollama, but it is still not responding. Ensure 'ollama' is installed and in your PATH.")
    else:
        print("    -> Ollama is already running.")

    print("\n[2] Starting Flask REST API (api/api.py) on Port 5000...")
    open_in_new_window(["python", "api/api.py"])

    # Step 3: Wait 2 seconds
    print("\n[3] Waiting 2 seconds for Flask API to initialize...")
    time.sleep(2)

    # Step 4: Start Streamlit Dashboard
    print("\n[4] Starting Streamlit Dashboard (dashboard/dashboard.py) on Port 8501...")
    open_in_new_window(["streamlit", "run", "dashboard/dashboard.py", "--server.headless", "true"])

    # Wait for streamlit to bind port
    print("\n[5] Waiting 3 seconds for Streamlit to build the frontend...")
    time.sleep(3)

    # Step 5: Start React Dashboard (news-weaver)
    print("\n[5] Starting React Dashboard (news-weaver)...")
    react_dir = os.path.join(os.path.dirname(__file__), "..", "news-weaver", "news-weaver-main")
    subprocess.Popen(
        ["cmd", "/K", f"cd /d {os.path.abspath(react_dir)} && npm run dev"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(4)

    # Step 6: Open Browser
    react_url = "http://localhost:5173"
    print(f"\n    -> Opening {react_url} in your default browser...")
    webbrowser.open(react_url)
    
    print("\n========================================")
    print(" All background services have been launched! ")
    print(" You can close this orchestrator window safely.")
    print("========================================")

if __name__ == "__main__":
    main()
