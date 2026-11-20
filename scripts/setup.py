#!/usr/bin/env python3
"""Setup script to verify project structure and dependencies."""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def check_project_structure():
    """Check if project structure is correct."""
    required_dirs = [
        "src",
        "src/api",
        "src/config", 
        "src/processing",
        "src/search",
        "src/highlighting",
        "src/llm",
        "tests"
    ]
    
    required_files = [
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
        "README.md",
        "src/api/main.py",
        "src/config/settings.py"
    ]
    
    print("Checking project structure...")
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"❌ Missing directory: {dir_path}")
            return False
        print(f"✅ Directory exists: {dir_path}")
    
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Missing file: {file_path}")
            return False
        print(f"✅ File exists: {file_path}")
    
    return True


def install_dependencies():
    """Install project dependencies."""
    print("Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def run_basic_tests():
    """Run basic tests to verify setup."""
    print("Running basic tests...")
    try:
        subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], 
                      check=True, capture_output=True)
        print("✅ Basic tests passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed: {e}")
        return False


def main():
    """Main setup verification."""
    print("🚀 Enterprise Document Assistant Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Project Structure", check_project_structure),
    ]
    
    for check_name, check_func in checks:
        print(f"\n{check_name}:")
        if not check_func():
            print(f"❌ Setup verification failed at: {check_name}")
            sys.exit(1)
    
    print("\n✅ Project structure setup completed successfully!")
    print("\nNext steps:")
    print("1. Create virtual environment: python -m venv venv")
    print("2. Activate virtual environment: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Copy .env.example to .env and configure your Azure credentials")
    print("5. Run the application: python -m src.api.main")


if __name__ == "__main__":
    main()