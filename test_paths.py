#!/usr/bin/env python3
"""
Test Path Configuration

Validates that the path configuration module works correctly and
enforces security boundaries.
"""

import tempfile
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.paths import (
    PathConfig,
    create_path_config,
    get_path_config,
    reset_path_config,
    detect_workspace_root
)
from orchestrator.preview_server import (
    PreviewServer,
    get_preview_server,
    reset_preview_server
)


def test_path_detection():
    """Test workspace root detection"""
    print("🧪 Testing path detection...")
    
    # Test detection without env override
    workspace = detect_workspace_root()
    print(f"   Detected workspace: {workspace}")
    assert workspace.exists(), "Workspace should exist"
    print("   ✅ Path detection works")


def test_path_config_creation():
    """Test path configuration creation"""
    print("\n🧪 Testing path config creation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create config
        config = create_path_config(tmppath)
        
        # Verify paths
        assert config.workspace_root == tmppath
        assert config.project_root == tmppath / "project"
        assert config.site_root == tmppath / "site"
        
        # Verify directories created
        assert config.workspace_root.exists()
        assert config.project_root.exists()
        assert config.site_root.exists()
        
        print(f"   WORKSPACE_ROOT: {config.workspace_root}")
        print(f"   PROJECT_ROOT: {config.project_root}")
        print(f"   SITE_ROOT: {config.site_root}")
        print("   ✅ Path config creation works")


def test_path_validation():
    """Test path validation guardrails"""
    print("\n🧪 Testing path validation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config = create_path_config(tmppath)
        
        # Test valid paths
        valid_path = config.project_root / "index.html"
        assert config.validate_path_in_project(valid_path), "Should accept path in project"
        print("   ✅ Valid path accepted")
        
        # Test invalid path (outside project)
        invalid_path = config.workspace_root / "outside.html"
        assert not config.validate_path_in_project(invalid_path), "Should reject path outside project"
        print("   ✅ Invalid path rejected")
        
        # Test path traversal attempt
        traversal_path = config.project_root / "../../../etc/passwd"
        assert not config.validate_path_in_project(traversal_path), "Should reject path traversal"
        print("   ✅ Path traversal blocked")


def test_safe_path_join():
    """Test safe path joining"""
    print("\n🧪 Testing safe path join...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config = create_path_config(tmppath)
        
        # Test valid join
        safe_path = config.safe_path_join("subdir", "file.html")
        assert safe_path.parent.name == "subdir"
        assert safe_path.name == "file.html"
        print(f"   ✅ Safe join works: {safe_path}")
        
        # Test invalid join (path traversal)
        try:
            bad_path = config.safe_path_join("..", "..", "etc", "passwd")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            print(f"   ✅ Path traversal blocked: {e}")


def test_preview_server():
    """Test preview server"""
    print("\n🧪 Testing preview server...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config = create_path_config(tmppath)
        
        # Create test file
        test_file = config.project_root / "test.html"
        test_file.write_text("<html><body>Test</body></html>")
        
        # Start server
        server = PreviewServer(
            serve_dir=config.project_root,
            host="127.0.0.1",
            port=8001  # Use different port for testing
        )
        server.start()
        
        try:
            # Verify server properties
            assert server.is_running, "Server should be running"
            assert server.url == "http://127.0.0.1:8001/"
            
            file_url = server.get_file_url("test.html")
            assert file_url == "http://127.0.0.1:8001/test.html"
            
            print(f"   Server URL: {server.url}")
            print(f"   File URL: {file_url}")
            print("   ✅ Preview server works")
            
        finally:
            server.stop()
            print("   ✅ Server stopped cleanly")


def test_preview_url_generation():
    """Test preview URL generation"""
    print("\n🧪 Testing preview URL generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config = create_path_config(tmppath)
        
        # Verify URL format
        assert config.preview_url.startswith("http://")
        assert not config.preview_url.startswith("file://")
        
        print(f"   Preview URL: {config.preview_url}")
        print("   ✅ URL format correct (HTTP, not file://)")


def test_singleton_pattern():
    """Test that get_path_config returns singleton"""
    print("\n🧪 Testing singleton pattern...")
    
    # Reset first
    reset_path_config()
    reset_preview_server()
    
    # Get config twice
    config1 = get_path_config()
    config2 = get_path_config()
    
    # Should be same instance
    assert config1 is config2, "Should return same instance"
    print("   ✅ Singleton pattern works")
    
    # Reset for other tests
    reset_path_config()
    reset_preview_server()


def test_startup_logging():
    """Test startup logging"""
    print("\n🧪 Testing startup logging...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        config = create_path_config(tmppath)
        
        # Create some test files
        (config.project_root / "test1.html").write_text("test")
        (config.project_root / "test2.js").write_text("test")
        
        # Log startup info (should not raise)
        try:
            config.log_startup_info()
            print("   ✅ Startup logging works")
        except Exception as e:
            assert False, f"Logging failed: {e}"


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("PATH CONFIGURATION TESTS")
    print("=" * 70)
    
    tests = [
        test_path_detection,
        test_path_config_creation,
        test_path_validation,
        test_safe_path_join,
        test_preview_server,
        test_preview_url_generation,
        test_singleton_pattern,
        test_startup_logging,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
