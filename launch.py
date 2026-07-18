import subprocess
import sys
import os
import time
import webbrowser

def main():
    print("========================================")
    print("      Starting Opinova Environment      ")
    print("========================================")
    
    script_path = os.path.join(os.path.dirname(__file__), "main.py")
    log_file_path = os.path.join(os.path.dirname(__file__), "backend_logs.txt")
    
    print(f"--> Any backend errors will be saved to: {log_file_path}")
    
    # Open log file to safely redirect IDLE output without crashing
    with open(log_file_path, "w") as log_file:
        
        # 1. Start Backend
        print("[1/2] Booting FastAPI Backend on port 8000...")
        backend_process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=log_file,
            stderr=log_file
        )
        
        # 2. Start Frontend Server
        print("[2/2] Booting Frontend Static Server on port 3000...")
        frontend_process = subprocess.Popen(
            [sys.executable, "-m", "http.server", "3000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        time.sleep(2) # Wait for servers to spin up
        
        print("\n✅ Servers are running!")
        print("🌐 Opening http://localhost:3000 in your browser...")
        webbrowser.open("http://localhost:3000")
        
        print("\nKeep this window open. Press Ctrl+C to shut down.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down servers...")
            backend_process.terminate()
            frontend_process.terminate()

if __name__ == "__main__":
    main()
