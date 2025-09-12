
# Optional helper to open the app via Python (for PyInstaller scenarios)
import os, subprocess, sys
def main():
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]
    subprocess.run(cmd, check=False)
if __name__ == "__main__":
    main()
