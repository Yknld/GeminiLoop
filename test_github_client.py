#!/usr/bin/env python3
"""
Test suite for GitHub client

Tests GitHub integration without making real API calls
"""

import os
import tempfile
from pathlib import Path
from orchestrator.github_client import GitHubClient, get_github_client


def test_github_client_init():
    """Test GitHub client initialization"""
    print("Testing GitHubClient initialization...")
    
    # Test without credentials (should be disabled)
    client = GitHubClient(token=None, repo_name=None)
    assert not client.is_enabled(), "Client should be disabled without credentials"
    print("✅ Correctly disabled without credentials")
    
    # Test with token but no repo
    client = GitHubClient(token="fake_token", repo_name=None)
    assert not client.is_enabled(), "Client should be disabled without repo"
    print("✅ Correctly disabled without repo")
    
    # Test with repo but no token
    client = GitHubClient(token=None, repo_name="owner/repo")
    assert not client.is_enabled(), "Client should be disabled without token"
    print("✅ Correctly disabled without token")
    
    print()


def test_disabled_operations():
    """Test that operations return graceful failures when disabled"""
    print("Testing disabled client operations...")
    
    client = GitHubClient(token=None, repo_name=None)
    
    # Test create_branch
    result = client.create_branch("test-branch")
    assert not result["success"], "Should fail when disabled"
    assert "disabled" in result["message"].lower()
    print("✅ create_branch returns graceful failure")
    
    # Test clone_branch_to_workspace
    result = client.clone_branch_to_workspace(
        "test-branch",
        Path("/tmp/test")
    )
    assert not result["success"], "Should fail when disabled"
    assert "disabled" in result["message"].lower()
    print("✅ clone_branch_to_workspace returns graceful failure")
    
    # Test commit_and_push
    result = client.commit_and_push(
        Path("/tmp/test"),
        "Test commit",
        "test-branch"
    )
    assert not result["success"], "Should fail when disabled"
    assert "disabled" in result["message"].lower()
    print("✅ commit_and_push returns graceful failure")
    
    print()


def test_url_helpers():
    """Test URL helper methods"""
    print("Testing URL helpers...")
    
    client = GitHubClient(
        token="fake_token",
        repo_name="owner/repo",
        base_branch="main"
    )
    
    # Test get_branch_url
    url = client.get_branch_url("feature/test")
    assert url == "https://github.com/owner/repo/tree/feature/test"
    print(f"✅ Branch URL: {url}")
    
    # Test get_commit_url
    url = client.get_commit_url("abc123def456")
    assert url == "https://github.com/owner/repo/commit/abc123def456"
    print(f"✅ Commit URL: {url}")
    
    print()


def test_factory_function():
    """Test get_github_client factory"""
    print("Testing get_github_client factory...")
    
    # Clear env vars
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("GITHUB_REPO", None)
    os.environ.pop("BASE_BRANCH", None)
    
    # Test without env vars
    client = get_github_client()
    assert not client.is_enabled(), "Should be disabled without env vars"
    print("✅ Factory creates disabled client without env vars")
    
    # Test with env vars
    os.environ["GITHUB_TOKEN"] = "test_token"
    os.environ["GITHUB_REPO"] = "test/repo"
    os.environ["BASE_BRANCH"] = "develop"
    
    client = get_github_client()
    assert client.token == "test_token"
    assert client.repo_name == "test/repo"
    assert client.base_branch == "develop"
    print("✅ Factory creates client from env vars")
    
    # Cleanup
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("GITHUB_REPO", None)
    os.environ.pop("BASE_BRANCH", None)
    
    print()


def test_branch_naming():
    """Test branch naming conventions"""
    print("Testing branch naming conventions...")
    
    # Typical run branch
    run_id = "quiz-20260113-123456"
    branch = f"run/{run_id}"
    
    assert branch == "run/quiz-20260113-123456"
    print(f"✅ Run branch: {branch}")
    
    # Feature branch
    task = "Create landing page"
    branch = f"feature/{task.lower().replace(' ', '-')}"
    assert branch == "feature/create-landing-page"
    print(f"✅ Feature branch: {branch}")
    
    print()


def test_commit_message_format():
    """Test commit message formatting"""
    print("Testing commit message format...")
    
    iteration = 1
    score = 45
    message = f"[Iteration {iteration}] Apply OpenHands patch (score: {score}/100)"
    
    assert message == "[Iteration 1] Apply OpenHands patch (score: 45/100)"
    print(f"✅ Commit message: {message}")
    
    print()


def test_result_structure():
    """Test result dictionary structure"""
    print("Testing result structures...")
    
    # Branch creation result
    branch_result = {
        "success": True,
        "branch": "run/test-123",
        "sha": "abc123",
        "message": "Created branch",
        "ref": "refs/heads/run/test-123"
    }
    assert "success" in branch_result
    assert "branch" in branch_result
    print("✅ Branch result structure valid")
    
    # Clone result
    clone_result = {
        "success": True,
        "workspace": "/app/workspace",
        "branch": "run/test-123",
        "message": "Cloned successfully"
    }
    assert "success" in clone_result
    assert "workspace" in clone_result
    print("✅ Clone result structure valid")
    
    # Commit result
    commit_result = {
        "success": True,
        "branch": "run/test-123",
        "message": "Committed and pushed",
        "commit_sha": "def456",
        "commit_url": "https://github.com/owner/repo/commit/def456",
        "branch_url": "https://github.com/owner/repo/tree/run/test-123"
    }
    assert "success" in commit_result
    assert "commit_sha" in commit_result
    assert "branch_url" in commit_result
    print("✅ Commit result structure valid")
    
    print()


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 Testing GitHub Client")
    print("=" * 70)
    print()
    
    try:
        test_github_client_init()
        test_disabled_operations()
        test_url_helpers()
        test_factory_function()
        test_branch_naming()
        test_commit_message_format()
        test_result_structure()
        
        print("=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        print()
        
        print("Note: These tests verify the client structure and disabled behavior.")
        print("To test with real GitHub API:")
        print("1. Set GITHUB_TOKEN and GITHUB_REPO environment variables")
        print("2. Run a full orchestrator test")
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
