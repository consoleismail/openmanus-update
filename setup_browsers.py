import os
import subprocess
import sys
from pathlib import Path

def setup_browsers():
    """
    Setup Playwright browsers in a persistent project directory.
    """
    project_root = Path(__file__).resolve().parent
    browsers_path = project_root / ".playwright-browsers"
    
    print(f"🚀 Setting up Playwright browsers in: {browsers_path}")
    
    # Create the directory if it doesn't exist
    browsers_path.mkdir(parents=True, exist_ok=True)
    
    # Set the environment variable for the current process and sub-processes
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
    
    try:
        # Check if playwright is installed in the environment
        subprocess.run([sys.executable, "-m", "playwright", "--version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ Playwright is not installed in the current Python environment.")
        print("Please run: pip install -r requirements.txt")
        return
    except FileNotFoundError:
        print("❌ Python executable not found.")
        return

    print("📥 Downloading Chromium...")
    try:
        # Run playwright install chromium
        # We use sys.executable -m playwright to ensure we use the correct environment
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env=os.environ,
            check=True
        )
        print("\n✅ Playwright browsers installed successfully!")
        print(f"📍 Location: {browsers_path}")
        print("\n💡 OpenManus is now configured to use these browsers automatically.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to install browsers: {e}")
        print("\nPossible reasons:")
        print("1. Network connection issues")
        print("2. Missing system dependencies (run 'playwright install-deps' if needed)")

if __name__ == "__main__":
    setup_browsers()
