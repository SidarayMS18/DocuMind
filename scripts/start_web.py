"""
Startup script for the Streamlit web interface.
"""

import subprocess
import sys
import os

def main():
    """Start the Streamlit web interface."""
    # Get the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_path = os.path.join(project_root, "src", "web", "app.py")
    
    print("Starting Enterprise Document Assistant Web Interface...")
    print(f"App path: {app_path}")
    print("Access the interface at: http://localhost:8501")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            app_path,
            "--server.port=8501",
            "--server.address=localhost"
        ])
    except KeyboardInterrupt:
        print("\nShutting down web interface...")
    except Exception as e:
        print(f"Error starting web interface: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
