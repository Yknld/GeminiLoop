#!/usr/bin/env python3
"""
Test Setup Script

Verifies that all dependencies and components are correctly installed
"""

import sys
import os
from pathlib import Path


def check_python_version():
    """Check Python version"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    
    if version >= (3, 11):
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} (need 3.11+)")
        return False


def check_python_packages():
    """Check Python packages"""
    print("\n📦 Checking Python packages...")
    
    packages = [
        "google.generativeai",
        "playwright",
        "fastapi",
        "uvicorn",
        "pydantic",
        "aiohttp"
    ]
    
    all_installed = True
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (not installed)")
            all_installed = False
    
    return all_installed


def check_node():
    """Check Node.js"""
    print("\n🟢 Checking Node.js...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ Node.js {version}")
            return True
        else:
            print(f"   ❌ Node.js not found")
            return False
    except Exception as e:
        print(f"   ❌ Node.js check failed: {e}")
        return False


def check_npm_packages():
    """Check npm packages"""
    print("\n📦 Checking npm packages...")
    
    package_json = Path("package.json")
    
    if not package_json.exists():
        print("   ❌ package.json not found")
        return False
    
    node_modules = Path("node_modules")
    
    if node_modules.exists():
        playwright = node_modules / "playwright"
        if playwright.exists():
            print("   ✅ playwright")
            return True
        else:
            print("   ❌ playwright (not installed)")
            return False
    else:
        print("   ❌ node_modules not found (run: npm install)")
        return False


def check_playwright_browsers():
    """Check Playwright browsers"""
    print("\n🌐 Checking Playwright browsers...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["npx", "playwright", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"   ✅ Playwright installed")
            
            # Check if chromium is installed
            # This is a simple check - in production you'd verify browser binaries
            print("   ℹ️  Run 'npx playwright install chromium' if browsers not installed")
            return True
        else:
            print(f"   ❌ Playwright not found")
            return False
    except Exception as e:
        print(f"   ❌ Playwright check failed: {e}")
        return False


def check_env_file():
    """Check environment file"""
    print("\n🔧 Checking environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("   ✅ .env file found")
        
        # Check if API key is set
        content = env_file.read_text()
        if "GOOGLE_AI_STUDIO_API_KEY" in content:
            if "your_api_key_here" not in content:
                print("   ✅ GOOGLE_AI_STUDIO_API_KEY appears to be set")
                return True
            else:
                print("   ⚠️  GOOGLE_AI_STUDIO_API_KEY not configured")
                print("      Edit .env and add your API key")
                return False
        else:
            print("   ❌ GOOGLE_AI_STUDIO_API_KEY not found in .env")
            return False
    else:
        if env_example.exists():
            print("   ⚠️  .env not found (copy from .env.example)")
        else:
            print("   ❌ .env and .env.example not found")
        return False


def check_directories():
    """Check required directories"""
    print("\n📁 Checking directory structure...")
    
    required = [
        "orchestrator",
        "services",
        "deploy/runpod",
        "assets"
    ]
    
    all_exist = True
    
    for dir_name in required:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ (missing)")
            all_exist = False
    
    return all_exist


def main():
    """Run all checks"""
    print("=" * 70)
    print("🔍 GeminiLoop Setup Verification")
    print("=" * 70)
    
    checks = [
        check_python_version(),
        check_python_packages(),
        check_node(),
        check_npm_packages(),
        check_playwright_browsers(),
        check_env_file(),
        check_directories()
    ]
    
    print("\n" + "=" * 70)
    
    if all(checks):
        print("✅ All checks passed! System is ready.")
        print("\nNext steps:")
        print("  1. Start preview server: python services/preview_server.py")
        print("  2. Run orchestrator: python -m orchestrator.main \"Your task\"")
        print("  3. Or run demo: python demo.py 0")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nQuick fix commands:")
        print("  - Install Python packages: pip install -r requirements.txt")
        print("  - Install npm packages: npm install")
        print("  - Install browsers: npx playwright install chromium")
        print("  - Setup env: cp .env.example .env && edit .env")
        return 1


if __name__ == "__main__":
    sys.exit(main())
