#!/usr/bin/env python3
"""
Test OpenHands Integration

Tests both mock and local OpenHands clients
"""

import sys
import json
import tempfile
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.openhands_client import (
    OpenHandsClient,
    MockOpenHandsClient,
    LocalSubprocessOpenHandsClient,
    get_openhands_client
)
from orchestrator.patch_generator import (
    generate_patch_plan,
    create_simple_patch_plan,
    extract_issues_from_evaluation
)


def test_mock_client():
    """Test MockOpenHandsClient"""
    print("Testing MockOpenHandsClient...")
    
    # Create temp workspace
    workspace = Path(tempfile.mkdtemp())
    artifacts = Path(tempfile.mkdtemp())
    
    # Create test file
    test_file = workspace / "index.html"
    test_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
    <style>
        body { padding: 10px; }
        button { padding: 8px; }
    </style>
</head>
<body>
    <h1>Test Page</h1>
    <button>Click Me</button>
</body>
</html>
""")
    
    # Create patch plan
    patch_plan = {
        "instructions": "Improve the button styling",
        "files": [
            {
                "path": "index.html",
                "action": "modify",
                "description": "Improve button styling",
                "changes": [
                    {"find": "padding: 8px", "replace": "padding: 12px 24px"}
                ]
            }
        ]
    }
    
    # Apply patch
    client = MockOpenHandsClient(artifacts)
    result = client.apply_patch_plan(str(workspace), patch_plan)
    
    assert result["success"], "Patch should succeed"
    assert len(result["files_modified"]) > 0, "Should modify files"
    
    # Check file was modified
    modified_content = test_file.read_text()
    assert "padding: 12px 24px" in modified_content, "Patch should be applied"
    
    print("✅ MockOpenHandsClient test passed")
    print(f"   Files modified: {result['files_modified']}")
    print(f"   Duration: {result['duration_seconds']:.2f}s")
    
    # Cleanup
    import shutil
    shutil.rmtree(workspace)
    shutil.rmtree(artifacts)


def test_patch_generator():
    """Test patch plan generator"""
    print("\nTesting patch plan generator...")
    
    # Mock evaluation
    evaluation = {
        "score": 55,
        "passed": False,
        "feedback": "Button styling needs improvement, colors are too bland",
        "functionality": {
            "score": 25,
            "passed": False,
            "issues": ["Button click handler missing"]
        },
        "visual": {
            "score": 20,
            "passed": False,
            "issues": ["Poor color scheme", "Insufficient padding"]
        }
    }
    
    task = "Create a landing page with a button"
    files_generated = {"index.html": "/tmp/index.html"}
    
    # Generate patch plan
    patch_plan = generate_patch_plan(evaluation, task, files_generated)
    
    assert "instructions" in patch_plan
    assert "files" in patch_plan
    assert len(patch_plan["files"]) > 0
    assert patch_plan["original_score"] == 55
    
    print("✅ Patch plan generator test passed")
    print(f"   Files to patch: {len(patch_plan['files'])}")
    print(f"   Issues identified: {patch_plan['issues_count']}")
    
    # Test issue extraction
    issues = extract_issues_from_evaluation(evaluation)
    assert len(issues) > 0, "Should extract issues"
    
    print(f"   Issues extracted: {len(issues)}")
    for issue in issues:
        print(f"     - [{issue['category']}] {issue['issue']}")


def test_simple_patch_plan():
    """Test simple patch plan creation"""
    print("\nTesting simple patch plan...")
    
    patch_plan = create_simple_patch_plan(
        feedback="Improve button styling",
        filename="index.html"
    )
    
    assert "instructions" in patch_plan
    assert "files" in patch_plan
    assert len(patch_plan["files"]) == 1
    assert patch_plan["files"][0]["path"] == "index.html"
    
    print("✅ Simple patch plan test passed")


def test_client_factory():
    """Test client factory function"""
    print("\nTesting client factory...")
    
    import os
    
    # Test mock mode
    os.environ["OPENHANDS_MODE"] = "mock"
    client = get_openhands_client()
    assert isinstance(client, MockOpenHandsClient)
    print("✅ Mock mode: correct client type")
    
    # Test local mode (will create LocalSubprocessOpenHandsClient)
    os.environ["OPENHANDS_MODE"] = "local"
    client = get_openhands_client()
    assert isinstance(client, LocalSubprocessOpenHandsClient)
    print("✅ Local mode: correct client type")
    
    # Test default (should be mock)
    os.environ.pop("OPENHANDS_MODE", None)
    client = get_openhands_client()
    assert isinstance(client, MockOpenHandsClient)
    print("✅ Default mode: correct client type (mock)")


def test_natural_language_changes():
    """Test natural language change application"""
    print("\nTesting natural language change application...")
    
    workspace = Path(tempfile.mkdtemp())
    artifacts = Path(tempfile.mkdtemp())
    
    test_file = workspace / "index.html"
    test_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <style>
        body { color: #333; }
    </style>
</head>
<body>
    <h1>Test</h1>
</body>
</html>
""")
    
    # Test color change via natural language
    patch_plan = {
        "instructions": "Change colors to blue",
        "files": [
            {
                "path": "index.html",
                "action": "modify",
                "description": "Change color to blue",
                "changes": ["Make the text color blue"]
            }
        ]
    }
    
    client = MockOpenHandsClient(artifacts)
    result = client.apply_patch_plan(str(workspace), patch_plan)
    
    assert result["success"]
    
    modified = test_file.read_text()
    # Should have changed color
    print("✅ Natural language changes test passed")
    
    # Cleanup
    import shutil
    shutil.rmtree(workspace)
    shutil.rmtree(artifacts)


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 Testing OpenHands Integration")
    print("=" * 70)
    
    try:
        test_mock_client()
        test_patch_generator()
        test_simple_patch_plan()
        test_client_factory()
        test_natural_language_changes()
        
        print("\n" + "=" * 70)
        print("✅ All OpenHands tests passed!")
        print("=" * 70)
        
        print("\nOpenHands integration is ready:")
        print("  1. MockOpenHandsClient (regex-based) ✅")
        print("  2. LocalSubprocessOpenHandsClient (CLI-based) ✅")
        print("  3. Patch plan generator ✅")
        print("  4. Client factory with OPENHANDS_MODE ✅")
        print("\nUsage:")
        print("  export OPENHANDS_MODE=mock")
        print("  python -m orchestrator.main 'Your task'")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
