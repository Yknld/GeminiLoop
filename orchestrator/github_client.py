"""
GitHub Client for GeminiLoop

Handles repository operations:
- Branch creation
- Cloning to workspace
- Commit and push

Uses PyGithub for API operations and git CLI for workspace operations.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from github import Github, GithubException
import logging

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    GitHub client for template branching workflow.
    
    Workflow:
    1. Clone template repo branch to workspace
    2. Create new branch for run
    3. Commit and push changes after patches
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        repo_name: Optional[str] = None,
        base_branch: str = "main"
    ):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (or from GITHUB_TOKEN env)
            repo_name: Repository name in format "owner/repo" (or from GITHUB_REPO env)
            base_branch: Base branch name (or from BASE_BRANCH env, default: "main")
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo_name = repo_name or os.getenv("GITHUB_REPO")
        self.base_branch = base_branch or os.getenv("BASE_BRANCH", "main")
        
        if not self.token:
            logger.warning("No GitHub token provided, GitHub operations will be disabled")
            self.enabled = False
            return
        
        if not self.repo_name:
            logger.warning("No GitHub repo provided, GitHub operations will be disabled")
            self.enabled = False
            return
        
        self.enabled = True
        self.github = Github(self.token)
        
        try:
            self.repo = self.github.get_repo(self.repo_name)
            logger.info(f"✅ Connected to GitHub repo: {self.repo_name}")
        except GithubException as e:
            logger.error(f"Failed to connect to GitHub repo: {e}")
            self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if GitHub operations are enabled."""
        return self.enabled
    
    def _initialize_empty_repo(self) -> Optional[str]:
        """
        Initialize an empty repository with a README.md file.
        
        Returns:
            str: SHA of the initial commit, or None if failed
        """
        try:
            # Create README.md content
            readme_content = "# GeminiLoop Artifacts\n\nThis repository contains generated course artifacts.\n"
            
            # Create file via API
            self.repo.create_file(
                path="README.md",
                message="Initial commit: Initialize repository",
                content=readme_content,
                branch=self.base_branch
            )
            
            # Get the commit SHA
            commit = self.repo.get_commits(sha=self.base_branch)[0]
            logger.info(f"✅ Initialized empty repository with README.md")
            return commit.sha
            
        except GithubException as e:
            logger.error(f"Failed to initialize empty repository: {e}")
            return None
    
    def create_branch(
        self,
        new_branch: str,
        base_branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new branch from base branch.
        
        Args:
            new_branch: Name of new branch to create
            base_branch: Base branch to branch from (default: self.base_branch)
        
        Returns:
            dict: {
                "success": bool,
                "branch": str,
                "sha": str,
                "message": str
            }
        """
        if not self.enabled:
            return {
                "success": False,
                "branch": new_branch,
                "message": "GitHub operations disabled"
            }
        
        base = base_branch or self.base_branch
        
        try:
            # Get base branch ref
            try:
                base_ref = self.repo.get_git_ref(f"heads/{base}")
                base_sha = base_ref.object.sha
            except GithubException as e:
                # Check if repo is empty
                if "Git Repository is empty" in str(e) or "404" in str(e):
                    logger.info(f"Repository is empty, initializing with README.md...")
                    init_sha = self._initialize_empty_repo()
                    if init_sha:
                        # Retry getting base branch ref
                        base_ref = self.repo.get_git_ref(f"heads/{base}")
                        base_sha = base_ref.object.sha
                    else:
                        raise GithubException(404, {"message": "Failed to initialize repository"})
                else:
                    raise
            
            # Check if branch already exists
            try:
                self.repo.get_git_ref(f"heads/{new_branch}")
                logger.warning(f"Branch {new_branch} already exists")
                return {
                    "success": True,
                    "branch": new_branch,
                    "sha": base_sha,
                    "message": f"Branch {new_branch} already exists",
                    "already_exists": True
                }
            except GithubException:
                pass  # Branch doesn't exist, we can create it
            
            # Create new branch
            new_ref = self.repo.create_git_ref(
                ref=f"refs/heads/{new_branch}",
                sha=base_sha
            )
            
            logger.info(f"✅ Created branch: {new_branch} from {base}")
            
            return {
                "success": True,
                "branch": new_branch,
                "sha": base_sha,
                "message": f"Created branch {new_branch} from {base}",
                "ref": new_ref.ref
            }
            
        except GithubException as e:
            logger.error(f"Failed to create branch {new_branch}: {e}")
            return {
                "success": False,
                "branch": new_branch,
                "message": f"Failed to create branch: {str(e)}"
            }
    
    def clone_branch_to_workspace(
        self,
        branch: str,
        workspace_path: Path,
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Clone a specific branch to workspace using shallow clone.
        
        Args:
            branch: Branch name to clone
            workspace_path: Path to clone into
            depth: Clone depth (default: 1 for shallow clone)
        
        Returns:
            dict: {
                "success": bool,
                "workspace": str,
                "branch": str,
                "message": str
            }
        """
        if not self.enabled:
            return {
                "success": False,
                "workspace": str(workspace_path),
                "branch": branch,
                "message": "GitHub operations disabled"
            }
        
        try:
            # Ensure workspace parent exists
            workspace_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Remove existing workspace if present
            if workspace_path.exists():
                import shutil
                shutil.rmtree(workspace_path)
                logger.info(f"Removed existing workspace: {workspace_path}")
            
            # Build clone URL with token
            clone_url = f"https://{self.token}@github.com/{self.repo_name}.git"
            
            # Clone with shallow depth
            cmd = [
                "git", "clone",
                "--branch", branch,
                "--depth", str(depth),
                clone_url,
                str(workspace_path)
            ]
            
            logger.info(f"Cloning {self.repo_name}:{branch} to {workspace_path}...")
            
            # Run git clone
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return {
                    "success": False,
                    "workspace": str(workspace_path),
                    "branch": branch,
                    "message": f"Git clone failed: {result.stderr}"
                }
            
            logger.info(f"✅ Cloned {branch} to {workspace_path}")
            
            return {
                "success": True,
                "workspace": str(workspace_path),
                "branch": branch,
                "message": f"Cloned {self.repo_name}:{branch}",
                "stdout": result.stdout
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Git clone timed out")
            return {
                "success": False,
                "workspace": str(workspace_path),
                "branch": branch,
                "message": "Git clone timed out"
            }
        except Exception as e:
            logger.error(f"Failed to clone branch: {e}")
            return {
                "success": False,
                "workspace": str(workspace_path),
                "branch": branch,
                "message": f"Failed to clone: {str(e)}"
            }
    
    def commit_and_push(
        self,
        workspace_path: Path,
        message: str,
        branch: str,
        add_all: bool = True
    ) -> Dict[str, Any]:
        """
        Commit changes in workspace and push to branch.
        
        Args:
            workspace_path: Path to git workspace
            message: Commit message
            branch: Branch to push to
            add_all: Whether to add all changes (default: True)
        
        Returns:
            dict: {
                "success": bool,
                "branch": str,
                "message": str,
                "commit_sha": str (if successful)
            }
        """
        if not self.enabled:
            return {
                "success": False,
                "branch": branch,
                "message": "GitHub operations disabled"
            }
        
        if not workspace_path.exists():
            return {
                "success": False,
                "branch": branch,
                "message": f"Workspace does not exist: {workspace_path}"
            }
        
        try:
            # Configure git user (required for commits)
            subprocess.run(
                ["git", "config", "user.name", "GeminiLoop"],
                cwd=workspace_path,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "gemini-loop@example.com"],
                cwd=workspace_path,
                check=True,
                capture_output=True
            )
            
            # Add changes
            if add_all:
                result = subprocess.run(
                    ["git", "add", "-A"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    logger.error(f"Git add failed: {result.stderr}")
                    return {
                        "success": False,
                        "branch": branch,
                        "message": f"Git add failed: {result.stderr}"
                    }
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if not status_result.stdout.strip():
                logger.info("No changes to commit")
                return {
                    "success": True,
                    "branch": branch,
                    "message": "No changes to commit",
                    "no_changes": True
                }
            
            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Git commit failed: {result.stderr}")
                return {
                    "success": False,
                    "branch": branch,
                    "message": f"Git commit failed: {result.stderr}"
                }
            
            # Get commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            commit_sha = sha_result.stdout.strip()
            
            # Push
            result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Git push failed: {result.stderr}")
                return {
                    "success": False,
                    "branch": branch,
                    "message": f"Git push failed: {result.stderr}",
                    "commit_sha": commit_sha
                }
            
            logger.info(f"✅ Committed and pushed to {branch}: {commit_sha[:7]}")
            
            # Build branch URL
            branch_url = f"https://github.com/{self.repo_name}/tree/{branch}"
            
            return {
                "success": True,
                "branch": branch,
                "message": f"Committed and pushed to {branch}",
                "commit_sha": commit_sha,
                "commit_url": f"https://github.com/{self.repo_name}/commit/{commit_sha}",
                "branch_url": branch_url,
                "stdout": result.stdout
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Git operation timed out")
            return {
                "success": False,
                "branch": branch,
                "message": "Git operation timed out"
            }
        except Exception as e:
            logger.error(f"Failed to commit and push: {e}")
            return {
                "success": False,
                "branch": branch,
                "message": f"Failed to commit and push: {str(e)}"
            }
    
    def get_branch_url(self, branch: str) -> str:
        """Get GitHub URL for a branch."""
        return f"https://github.com/{self.repo_name}/tree/{branch}"
    
    def get_commit_url(self, commit_sha: str) -> str:
        """Get GitHub URL for a commit."""
        return f"https://github.com/{self.repo_name}/commit/{commit_sha}"
    
    def push_artifacts(
        self,
        workspace_path: Path,
        artifacts_dir: Path,
        branch: str,
        commit_message: Optional[str] = None,
        artifacts_subdir: str = "artifacts"
    ) -> Dict[str, Any]:
        """
        Push screenshots and videos to GitHub artifacts directory.
        
        Args:
            workspace_path: Path to git workspace
            artifacts_dir: Directory containing screenshots/videos to push
            branch: Branch to push to
            commit_message: Custom commit message (default: auto-generated)
            artifacts_subdir: Subdirectory in repo for artifacts (default: "artifacts")
        
        Returns:
            dict: {
                "success": bool,
                "branch": str,
                "message": str,
                "files_pushed": List[str],
                "commit_sha": str (if successful)
            }
        """
        if not self.enabled:
            return {
                "success": False,
                "branch": branch,
                "message": "GitHub operations disabled",
                "files_pushed": []
            }
        
        if not artifacts_dir.exists():
            return {
                "success": False,
                "branch": branch,
                "message": f"Artifacts directory does not exist: {artifacts_dir}",
                "files_pushed": []
            }
        
        try:
            import shutil
            
            # Target directory in workspace
            target_dir = workspace_path / artifacts_subdir
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Find screenshots and videos
            screenshot_extensions = {".png", ".jpg", ".jpeg", ".webp"}
            video_extensions = {".webm", ".mp4", ".mov"}
            
            files_pushed = []
            
            # Copy screenshots
            for ext in screenshot_extensions:
                for screenshot_file in artifacts_dir.rglob(f"*{ext}"):
                    if screenshot_file.is_file():
                        rel_path = screenshot_file.relative_to(artifacts_dir)
                        dest_file = target_dir / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(screenshot_file, dest_file)
                        files_pushed.append(str(rel_path))
                        logger.info(f"   Copied screenshot: {rel_path}")
            
            # Copy videos
            for ext in video_extensions:
                for video_file in artifacts_dir.rglob(f"*{ext}"):
                    if video_file.is_file():
                        rel_path = video_file.relative_to(artifacts_dir)
                        dest_file = target_dir / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(video_file, dest_file)
                        files_pushed.append(str(rel_path))
                        logger.info(f"   Copied video: {rel_path}")
            
            if not files_pushed:
                logger.info("No screenshots or videos found to push")
                return {
                    "success": True,
                    "branch": branch,
                    "message": "No artifacts to push",
                    "files_pushed": [],
                    "no_artifacts": True
                }
            
            # Generate commit message if not provided
            if not commit_message:
                screenshot_count = sum(1 for f in files_pushed if any(f.endswith(ext) for ext in screenshot_extensions))
                video_count = sum(1 for f in files_pushed if any(f.endswith(ext) for ext in video_extensions))
                commit_message = f"Add artifacts: {screenshot_count} screenshot(s), {video_count} video(s)"
            
            # Commit and push
            push_result = self.commit_and_push(
                workspace_path=workspace_path,
                message=commit_message,
                branch=branch,
                add_all=True
            )
            
            if push_result["success"]:
                logger.info(f"✅ Pushed {len(files_pushed)} artifacts to {branch}")
                return {
                    "success": True,
                    "branch": branch,
                    "message": f"Pushed {len(files_pushed)} artifacts",
                    "files_pushed": files_pushed,
                    "commit_sha": push_result.get("commit_sha"),
                    "commit_url": push_result.get("commit_url"),
                    "branch_url": push_result.get("branch_url")
                }
            else:
                return {
                    "success": False,
                    "branch": branch,
                    "message": push_result.get("message", "Failed to push artifacts"),
                    "files_pushed": files_pushed
                }
        
        except Exception as e:
            logger.error(f"Failed to push artifacts: {e}")
            return {
                "success": False,
                "branch": branch,
                "message": f"Failed to push artifacts: {str(e)}",
                "files_pushed": files_pushed if 'files_pushed' in locals() else []
            }
    
    def push_screenshots_and_videos(
        self,
        workspace_path: Path,
        screenshots_dir: Path,
        videos_dir: Optional[Path] = None,
        branch: str = None,
        iteration: Optional[int] = None,
        score: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to push screenshots and videos from evaluation.
        
        This method searches both screenshots_dir and videos_dir for artifacts
        and pushes them to GitHub in the artifacts/ subdirectory.
        
        Args:
            workspace_path: Path to git workspace
            screenshots_dir: Directory containing screenshots
            videos_dir: Optional directory containing videos (if None, searches screenshots_dir)
            branch: Branch to push to (default: uses workspace branch)
            iteration: Optional iteration number for commit message
            score: Optional score for commit message
        
        Returns:
            dict: Result from push_artifacts with files_pushed list
        """
        if not branch:
            # Try to get branch from workspace
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
                else:
                    branch = self.base_branch
            except:
                branch = self.base_branch
        
        # Collect artifacts from both directories
        import shutil
        target_dir = workspace_path / "artifacts"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        screenshot_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        video_extensions = {".webm", ".mp4", ".mov"}
        files_pushed = []
        
        # Copy screenshots from screenshots_dir
        for ext in screenshot_extensions:
            for screenshot_file in screenshots_dir.rglob(f"*{ext}"):
                if screenshot_file.is_file():
                    rel_path = screenshot_file.relative_to(screenshots_dir.parent if screenshots_dir.parent != screenshots_dir else screenshots_dir)
                    dest_file = target_dir / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(screenshot_file, dest_file)
                    files_pushed.append(str(rel_path))
                    logger.info(f"   Copied screenshot: {rel_path}")
        
        # Copy videos from videos_dir (if specified) or screenshots_dir
        search_dirs = [videos_dir] if videos_dir and videos_dir.exists() else [screenshots_dir]
        for search_dir in search_dirs:
            for ext in video_extensions:
                for video_file in search_dir.rglob(f"*{ext}"):
                    if video_file.is_file():
                        # Use relative path from search_dir's parent to maintain structure
                        rel_path = video_file.relative_to(search_dir.parent if search_dir.parent != search_dir else search_dir)
                        dest_file = target_dir / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(video_file, dest_file)
                        files_pushed.append(str(rel_path))
                        logger.info(f"   Copied video: {rel_path}")
        
        if not files_pushed:
            logger.info("No screenshots or videos found to push")
            return {
                "success": True,
                "branch": branch,
                "message": "No artifacts to push",
                "files_pushed": [],
                "no_artifacts": True
            }
        
        # Generate commit message
        commit_parts = []
        if iteration is not None:
            commit_parts.append(f"Iteration {iteration}")
        if score is not None:
            commit_parts.append(f"score: {score}/100")
        commit_message = f"Add evaluation artifacts"
        if commit_parts:
            commit_message += f" ({', '.join(commit_parts)})"
        
        # Commit and push
        push_result = self.commit_and_push(
            workspace_path=workspace_path,
            message=commit_message,
            branch=branch,
            add_all=True
        )
        
        if push_result["success"]:
            logger.info(f"✅ Pushed {len(files_pushed)} artifacts to {branch}")
            return {
                "success": True,
                "branch": branch,
                "message": f"Pushed {len(files_pushed)} artifacts",
                "files_pushed": files_pushed,
                "commit_sha": push_result.get("commit_sha"),
                "commit_url": push_result.get("commit_url"),
                "branch_url": push_result.get("branch_url")
            }
        else:
            return {
                "success": False,
                "branch": branch,
                "message": push_result.get("message", "Failed to push artifacts"),
                "files_pushed": files_pushed
            }


def get_github_client() -> GitHubClient:
    """
    Factory function to create GitHub client from environment variables.
    
    Returns:
        GitHubClient instance configured from env
    """
    return GitHubClient(
        token=os.getenv("GITHUB_TOKEN"),
        repo_name=os.getenv("GITHUB_REPO"),
        base_branch=os.getenv("BASE_BRANCH", "main")
    )
