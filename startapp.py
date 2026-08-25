import os
import subprocess
import sys

def main():
    # Change directory to backend
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    os.chdir(backend_dir)
    
    # Run python main.py serve
    print("Starting Opinova...")
    subprocess.run([sys.executable, "main.py", "serve"])

if __name__ == "__main__":
    main()
