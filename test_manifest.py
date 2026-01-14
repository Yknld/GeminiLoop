#!/usr/bin/env python3
"""
Test suite for run manifest

Tests manifest generation and structure
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from orchestrator.run_state import RunManifest, RunConfig, RunState


def test_manifest_creation():
    """Test creating a manifest"""
    print("Testing manifest creation...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Test task",
        start_time=datetime.now(),
        max_iterations=2
    )
    
    assert manifest.run_id == "test-123"
    assert manifest.task == "Test task"
    assert manifest.max_iterations == 2
    assert manifest.iteration_count == 0
    assert manifest.stop_reason == "unknown"
    assert not manifest.github_enabled
    
    print("✅ Manifest created with correct defaults")
    print()


def test_manifest_completion():
    """Test completing a manifest"""
    print("Testing manifest completion...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Test task",
        start_time=datetime.now()
    )
    
    # Complete with passed
    manifest.complete("passed")
    
    assert manifest.stop_reason == "passed"
    assert manifest.end_time is not None
    assert manifest.duration_seconds > 0
    
    print(f"✅ Manifest completed with stop_reason: {manifest.stop_reason}")
    print(f"   Duration: {manifest.duration_seconds:.3f}s")
    print()


def test_manifest_github_commits():
    """Test adding GitHub commits to manifest"""
    print("Testing GitHub commit tracking...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Test task",
        start_time=datetime.now(),
        github_enabled=True,
        github_repo="username/repo",
        github_branch="run/test-123"
    )
    
    # Add commits
    manifest.add_commit(
        iteration=1,
        commit_sha="abc123def456",
        commit_url="https://github.com/username/repo/commit/abc123def456"
    )
    
    manifest.add_commit(
        iteration=2,
        commit_sha="ghi789jkl012",
        commit_url="https://github.com/username/repo/commit/ghi789jkl012"
    )
    
    assert len(manifest.github_commits) == 2
    assert manifest.github_commits[0]["iteration"] == 1
    assert manifest.github_commits[0]["commit_sha"] == "abc123def456"
    assert manifest.github_commits[1]["iteration"] == 2
    
    print("✅ GitHub commits tracked correctly")
    print(f"   Commits: {len(manifest.github_commits)}")
    for commit in manifest.github_commits:
        print(f"   - Iteration {commit['iteration']}: {commit['commit_sha'][:7]}")
    print()


def test_manifest_serialization():
    """Test manifest to_dict and to_json"""
    print("Testing manifest serialization...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Test task",
        start_time=datetime.now(),
        gemini_model_version="gemini-2.0-flash-exp",
        evaluator_model_version="gemini-2.0-flash-exp",
        rubric_version="1.0",
        openhands_mode="mock"
    )
    
    manifest.iteration_count = 2
    manifest.final_score = 85
    manifest.final_passed = True
    manifest.complete("passed")
    
    # Test to_dict
    data = manifest.to_dict()
    assert isinstance(data, dict)
    assert data["run_id"] == "test-123"
    assert data["iteration_count"] == 2
    assert data["final_score"] == 85
    assert data["stop_reason"] == "passed"
    assert isinstance(data["start_time"], str)  # Should be ISO format
    
    print("✅ Manifest to_dict works correctly")
    
    # Test to_json
    json_str = manifest.to_json()
    parsed = json.loads(json_str)
    assert parsed["run_id"] == "test-123"
    assert parsed["gemini_model_version"] == "gemini-2.0-flash-exp"
    assert parsed["rubric_version"] == "1.0"
    
    print("✅ Manifest to_json works correctly")
    print()


def test_manifest_with_run_state():
    """Test manifest integration with RunState"""
    print("Testing manifest with RunState...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        config = RunConfig(
            task="Test integration",
            max_iterations=2,
            base_dir=base_dir
        )
        
        state = RunState(config)
        
        # Check manifest was created
        assert state.manifest is not None
        assert state.manifest.run_id == config.run_id
        assert state.manifest.task == "Test integration"
        assert state.manifest.max_iterations == 2
        
        print("✅ Manifest created with RunState")
        
        # Update manifest
        state.manifest.iteration_count = 1
        state.manifest.final_score = 75
        state.manifest.github_enabled = True
        state.manifest.github_repo = "test/repo"
        
        # Save manifest
        manifest_file = state.save_manifest()
        
        assert manifest_file.exists()
        assert manifest_file.name == "manifest.json"
        
        print(f"✅ Manifest saved to: {manifest_file}")
        
        # Load and verify
        with open(manifest_file) as f:
            data = json.load(f)
        
        assert data["run_id"] == config.run_id
        assert data["iteration_count"] == 1
        assert data["final_score"] == 75
        assert data["github_enabled"] is True
        assert data["github_repo"] == "test/repo"
        
        print("✅ Manifest data verified")
        print()


def test_manifest_fields():
    """Test all manifest fields"""
    print("Testing all manifest fields...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Complete test",
        start_time=datetime.now(),
        gemini_model_version="gemini-2.0-flash-exp",
        evaluator_model_version="gemini-2.0-flash-exp",
        rubric_version="1.0",
        openhands_mode="mock",
        max_iterations=3,
        iteration_count=2,
        final_score=82,
        final_passed=True,
        github_enabled=True,
        github_repo="username/repo",
        github_branch="run/test-123",
        github_base_branch="main",
        workspace_dir="/app/workspace",
        artifacts_dir="/app/artifacts",
        site_dir="/app/site",
        preview_url="http://localhost:8080/preview/test-123/"
    )
    
    manifest.add_commit(1, "abc123", "https://github.com/...")
    manifest.complete("passed")
    
    data = manifest.to_dict()
    
    # Verify all required fields
    required_fields = [
        "run_id", "task", "start_time", "end_time", "duration_seconds",
        "gemini_model_version", "evaluator_model_version", "rubric_version",
        "openhands_mode", "max_iterations", "iteration_count",
        "final_score", "final_passed", "stop_reason",
        "github_enabled", "github_repo", "github_branch", "github_base_branch",
        "github_commits", "workspace_dir", "artifacts_dir", "site_dir",
        "preview_url", "error_message"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing field: {field}"
    
    print("✅ All manifest fields present")
    print(f"   Fields: {len(data.keys())}")
    print()


def test_stop_reasons():
    """Test different stop reasons"""
    print("Testing stop reasons...")
    
    reasons = ["passed", "max_iterations", "failed", "error", "completed"]
    
    for reason in reasons:
        manifest = RunManifest(
            run_id=f"test-{reason}",
            task="Test",
            start_time=datetime.now()
        )
        manifest.complete(reason)
        
        assert manifest.stop_reason == reason
        print(f"   ✅ {reason}")
    
    print()


def test_manifest_json_structure():
    """Test JSON output structure"""
    print("Testing JSON structure...")
    
    manifest = RunManifest(
        run_id="test-123",
        task="Test task",
        start_time=datetime.now()
    )
    
    manifest.iteration_count = 2
    manifest.final_score = 85
    manifest.github_enabled = True
    manifest.github_repo = "user/repo"
    manifest.add_commit(1, "abc", "http://...")
    manifest.complete("passed")
    
    json_str = manifest.to_json()
    print(f"Manifest JSON preview:")
    print(json_str[:500] + "...")
    print()
    
    # Parse and validate
    data = json.loads(json_str)
    assert isinstance(data["github_commits"], list)
    assert len(data["github_commits"]) == 1
    assert isinstance(data["duration_seconds"], (int, float))
    
    print("✅ JSON structure valid")
    print()


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 Testing Run Manifest")
    print("=" * 70)
    print()
    
    try:
        test_manifest_creation()
        test_manifest_completion()
        test_manifest_github_commits()
        test_manifest_serialization()
        test_manifest_with_run_state()
        test_manifest_fields()
        test_stop_reasons()
        test_manifest_json_structure()
        
        print("=" * 70)
        print("✅ All manifest tests passed!")
        print("=" * 70)
        print()
        
        print("Manifest includes:")
        print("  ✅ Run identification (run_id, task)")
        print("  ✅ Timestamps (start, end, duration)")
        print("  ✅ Model versions (Gemini, evaluator, rubric)")
        print("  ✅ Iteration count and scores")
        print("  ✅ GitHub commits (if enabled)")
        print("  ✅ Stop reason (passed, max_iterations, error, etc.)")
        print("  ✅ Artifact paths")
        print()
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
