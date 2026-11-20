#!/usr/bin/env python3
"""Start the complete system: API + Frontend + n8n (optional)."""

import subprocess
import sys
import time
import os
from pathlib import Path

def start_api_server():
    """Start FastAPI backend server."""
    print("🚀 Starting FastAPI backend server...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=Path(__file__).parent.parent
    )
    return api_process

def start_frontend():
    """Start React frontend development server."""
    print("🎨 Starting React frontend...")
    frontend_dir = Path(__file__).parent.parent / "frontend"
    
    if not (frontend_dir / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    
    frontend_process = subprocess.Popen(
        ["npm", "start"],
        cwd=frontend_dir,
        shell=True
    )
    return frontend_process

def main():
    """Start all services."""
    print("=" * 60)
    print("🚀 TEMPLATE-DRIVEN DOCUMENT GENERATOR")
    print("=" * 60)
    print()
    
    processes = []
    
    try:
        # Start API
        api_proc = start_api_server()
        processes.append(("API Server", api_proc))
        time.sleep(3)
        
        # Start Frontend
        frontend_proc = start_frontend()
        processes.append(("Frontend", frontend_proc))
        
        print()
        print("=" * 60)
        print("✅ System Started Successfully!")
        print("=" * 60)
        print()
        print("📍 API Server:      http://localhost:8000")
        print("📍 API Docs:        http://localhost:8000/docs")
        print("📍 Frontend:        http://localhost:3000")
        print()
        print("💡 Optional: Start n8n separately with: docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n")
        print()
        print("Press Ctrl+C to stop all services...")
        print()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down services...")
        for name, proc in processes:
            print(f"   Stopping {name}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ All services stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
