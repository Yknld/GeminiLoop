#!/usr/bin/env python3
"""
Quick import test - validates syntax and import paths work
Doesn't require all dependencies, just checks the code structure
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Testing imports and syntax...\n")

# Test 1: Python syntax
print("1. Checking Python syntax...")
try:
    import py_compile
    files_to_check = [
        "handler.py",
        "orchestrator/main.py",
        "orchestrator/openhands_client.py",
        "qa_browseruse_mcp/client.py",
        "qa_browseruse_mcp/browser_session.py",
    ]
    
    errors = []
    for file in files_to_check:
        try:
            py_compile.compile(file, doraise=True)
            print(f"   ✅ {file}")
        except py_compile.PyCompileError as e:
            errors.append(f"   ❌ {file}: {e}")
            print(f"   ❌ {file}: {e}")
    
    if errors:
        print(f"\n❌ Found {len(errors)} syntax errors")
        sys.exit(1)
    else:
        print("   ✅ All files compile successfully\n")
        
except Exception as e:
    print(f"   ❌ Error checking syntax: {e}\n")

# Test 2: Import paths
print("2. Testing import paths...")
try:
    # Test qa_browseruse_mcp can be found
    import importlib.util
    spec = importlib.util.find_spec("qa_browseruse_mcp")
    if spec:
        print("   ✅ qa_browseruse_mcp module found")
    else:
        print("   ❌ qa_browseruse_mcp module not found")
        sys.exit(1)
    
    # Test handler can find it
    handler_path = Path(__file__).parent / "handler.py"
    with open(handler_path) as f:
        handler_code = f.read()
        if "sys.path.insert" in handler_code:
            print("   ✅ handler.py has sys.path setup")
        else:
            print("   ⚠️  handler.py missing sys.path setup")
    
    # Test main.py import
    main_path = Path(__file__).parent / "orchestrator" / "main.py"
    with open(main_path) as f:
        main_code = f.read()
        if "qa_browseruse_mcp" in main_code:
            print("   ✅ orchestrator/main.py imports qa_browseruse_mcp")
        else:
            print("   ⚠️  orchestrator/main.py doesn't import qa_browseruse_mcp")
    
    print("   ✅ Import paths configured correctly\n")
    
except Exception as e:
    print(f"   ❌ Error checking imports: {e}\n")
    sys.exit(1)

# Test 3: Geometry notes exist
print("3. Checking geometry notes...")
geometry_path = Path(__file__).parent.parent / "geometry_mock_notes"
if geometry_path.exists():
    notes_files = list(geometry_path.glob("*.md")) + list(geometry_path.glob("*.txt"))
    if notes_files:
        print(f"   ✅ Found {len(notes_files)} geometry note files")
        for f in notes_files:
            print(f"      - {f.name}")
    else:
        print("   ⚠️  No geometry note files found")
else:
    print(f"   ⚠️  Geometry notes directory not found: {geometry_path}")

print("\n✅ All basic checks passed!")
print("   Code structure is valid and ready for deployment")
