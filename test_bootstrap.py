#!/usr/bin/env python3
"""
Test Template Bootstrap

Validates that template bootstrap works correctly.
"""

import tempfile
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.bootstrap import (
    TemplateConfig,
    TemplateBootstrap,
    bootstrap_from_template
)


def test_config_from_env():
    """Test config creation from environment"""
    print("🧪 Testing config from environment...")
    
    # Set test env vars
    os.environ["TEMPLATE_REPO_URL"] = "https://github.com/test/repo.git"
    os.environ["TEMPLATE_REF"] = "develop"
    os.environ["PROJECT_DIR_NAME"] = "webapp"
    os.environ["RUN_TEMPLATE_INIT"] = "true"
    os.environ["PUBLISH_TO_SITE"] = "true"
    
    config = TemplateConfig.from_env()
    
    assert config.repo_url == "https://github.com/test/repo.git"
    assert config.ref == "develop"
    assert config.project_dir_name == "webapp"
    assert config.run_init == True
    assert config.publish_to_site == True
    assert config.is_enabled() == True
    
    print("   ✅ Config from environment works")
    
    # Clean up
    del os.environ["TEMPLATE_REPO_URL"]
    del os.environ["TEMPLATE_REF"]
    del os.environ["PROJECT_DIR_NAME"]
    del os.environ["RUN_TEMPLATE_INIT"]
    del os.environ["PUBLISH_TO_SITE"]


def test_config_disabled():
    """Test that config is disabled without repo URL"""
    print("\n🧪 Testing config disabled...")
    
    config = TemplateConfig()
    assert config.is_enabled() == False
    print("   ✅ Config correctly disabled without repo URL")


def test_bootstrap_disabled():
    """Test bootstrap when disabled"""
    print("\n🧪 Testing bootstrap disabled...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create config without repo URL (disabled)
        config = TemplateConfig()
        
        # Bootstrap should return disabled status
        result = bootstrap_from_template(tmppath, config)
        
        assert result["enabled"] == False
        assert "disabled" in result["message"].lower()
        
        print("   ✅ Bootstrap correctly skips when disabled")


def test_bootstrap_initialization():
    """Test bootstrap class initialization"""
    print("\n🧪 Testing bootstrap initialization...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        config = TemplateConfig(
            repo_url="https://github.com/test/repo.git",
            project_dir_name="custom-project"
        )
        
        bootstrap = TemplateBootstrap(tmppath, config)
        
        assert bootstrap.workspace_root == tmppath
        assert bootstrap.project_root == tmppath / "custom-project"
        assert bootstrap.config.repo_url == "https://github.com/test/repo.git"
        
        print("   ✅ Bootstrap initialization works")


def test_clean_project_dir():
    """Test safe project directory cleaning"""
    print("\n🧪 Testing project directory cleaning...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create project with some files
        project_dir = tmppath / "project"
        project_dir.mkdir()
        (project_dir / "file1.txt").write_text("content1")
        (project_dir / "file2.txt").write_text("content2")
        (project_dir / "subdir").mkdir()
        (project_dir / "subdir" / "file3.txt").write_text("content3")
        
        # Bootstrap should clean it
        config = TemplateConfig(
            repo_url="https://github.com/test/repo.git"
        )
        bootstrap = TemplateBootstrap(tmppath, config)
        bootstrap._clean_project_dir()
        
        # Directory should be gone
        assert not project_dir.exists()
        
        print("   ✅ Project directory cleaning works")


def test_clean_safety_check():
    """Test that cleaning refuses to delete outside workspace"""
    print("\n🧪 Testing clean safety check...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        outside_path = Path("/tmp/outside")
        
        config = TemplateConfig(
            repo_url="https://github.com/test/repo.git"
        )
        
        # Manually set project_root to outside path
        bootstrap = TemplateBootstrap(tmppath, config)
        bootstrap.project_root = outside_path
        
        # Create the outside directory
        outside_path.mkdir(exist_ok=True)
        
        try:
            # Should raise RuntimeError due to safety check
            bootstrap._clean_project_dir()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Safety check failed" in str(e)
            print("   ✅ Safety check works")
        finally:
            # Clean up
            if outside_path.exists():
                outside_path.rmdir()


def test_project_structure_logging():
    """Test project structure logging"""
    print("\n🧪 Testing project structure logging...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create project with files
        project_dir = tmppath / "project"
        project_dir.mkdir()
        (project_dir / "index.html").write_text("<html></html>")
        (project_dir / "styles.css").write_text("body{}")
        (project_dir / "subdir").mkdir()
        (project_dir / "subdir" / "script.js").write_text("console.log('test')")
        
        config = TemplateConfig(
            repo_url="https://github.com/test/repo.git"
        )
        bootstrap = TemplateBootstrap(tmppath, config)
        
        # Should not raise
        try:
            bootstrap._log_project_structure()
            file_count = bootstrap._count_files()
            assert file_count == 3, f"Expected 3 files, got {file_count}"
            print("   ✅ Project structure logging works")
        except Exception as e:
            assert False, f"Logging failed: {e}"


def test_publish_to_site():
    """Test publishing to SITE_ROOT"""
    print("\n🧪 Testing publish to site...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create project with files
        project_dir = tmppath / "project"
        project_dir.mkdir()
        (project_dir / "index.html").write_text("<html></html>")
        (project_dir / "styles.css").write_text("body{}")
        
        # Create site directory
        site_dir = tmppath / "site"
        
        # Test with publish disabled
        config = TemplateConfig(
            repo_url="https://github.com/test/repo.git",
            publish_to_site=False
        )
        bootstrap = TemplateBootstrap(tmppath, config)
        result = bootstrap.publish_to_site(site_dir)
        
        assert result["enabled"] == False
        print("   ✅ Publish correctly disabled")
        
        # Test with publish enabled
        config.publish_to_site = True
        bootstrap = TemplateBootstrap(tmppath, config)
        result = bootstrap.publish_to_site(site_dir)
        
        assert result["enabled"] == True
        assert result["success"] == True
        assert result["files_copied"] == 2
        assert (site_dir / "index.html").exists()
        assert (site_dir / "styles.css").exists()
        
        print("   ✅ Publish to site works")


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("TEMPLATE BOOTSTRAP TESTS")
    print("=" * 70)
    
    tests = [
        test_config_from_env,
        test_config_disabled,
        test_bootstrap_disabled,
        test_bootstrap_initialization,
        test_clean_project_dir,
        test_clean_safety_check,
        test_project_structure_logging,
        test_publish_to_site,
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
    
    if failed == 0:
        print("\n✅ All tests passed!")
        print("\n📝 Note: Git clone tests skipped (require actual repository)")
        print("   To test git cloning, set TEMPLATE_REPO_URL and run manually:")
        print("   export TEMPLATE_REPO_URL=https://github.com/your-org/template.git")
        print("   python -m orchestrator.main 'Test task'")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
