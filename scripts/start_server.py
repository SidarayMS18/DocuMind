#!/usr/bin/env python3
"""Script to start the FastAPI development server."""

import sys
import subprocess
from pathlib import Path

def main():
    """Start the development server."""
    print("🚀 Starting Enterprise Document Assistant Development Server")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("src/api/main.py").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    print("📍 Starting server at http://localhost:8000")
    print("📖 API documentation will be available at http://localhost:8000/docs")
    print("🔍 Health check endpoint: http://localhost:8000/health")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 60)
    
    try:
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "src.api.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()