"""
Template Bootstrap Module

Clones a Git template repository at the start of each OpenHands job to ensure
consistent file paths and project layout.

Configuration via environment variables:
- TEMPLATE_REPO_URL: Git repository URL (required)
- TEMPLATE_REF: Branch/tag/commit to checkout (default: main)
- PROJECT_DIR_NAME: Directory name for project (default: project)
- RUN_TEMPLATE_INIT: Run init script if present (default: false)
- PUBLISH_TO_SITE: Copy output to SITE_ROOT (default: false)
"""

import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TemplateConfig:
    """Configuration for template bootstrap"""
    
    # Git repository URL (required)
    repo_url: Optional[str] = None
    
    # Git ref to checkout (branch, tag, or commit)
    ref: str = "main"
    
    # Project directory name (relative to WORKSPACE_ROOT)
    project_dir_name: str = "project"
    
    # Run template init script if present
    run_init: bool = False
    
    # Copy output to SITE_ROOT for evaluator compatibility
    publish_to_site: bool = False
    
    @classmethod
    def from_env(cls) -> 'TemplateConfig':
        """Create config from environment variables"""
        return cls(
            repo_url=os.getenv("TEMPLATE_REPO_URL"),
            ref=os.getenv("TEMPLATE_REF", "main"),
            project_dir_name=os.getenv("PROJECT_DIR_NAME", "project"),
            run_init=os.getenv("RUN_TEMPLATE_INIT", "false").lower() in ("true", "1", "yes"),
            publish_to_site=os.getenv("PUBLISH_TO_SITE", "false").lower() in ("true", "1", "yes")
        )
    
    def is_enabled(self) -> bool:
        """Check if template bootstrap is enabled"""
        return self.repo_url is not None and self.repo_url.strip() != ""


class TemplateBootstrap:
    """
    Handles template repository cloning and initialization
    
    Ensures each OpenHands job starts from a clean, consistent template.
    """
    
    def __init__(self, workspace_root: Path, config: TemplateConfig):
        self.workspace_root = Path(workspace_root)
        self.config = config
        self.project_root = self.workspace_root / config.project_dir_name
        
        logger.info("Template bootstrap initialized:")
        logger.info(f"  Workspace root: {self.workspace_root}")
        logger.info(f"  Project root: {self.project_root}")
        logger.info(f"  Template enabled: {config.is_enabled()}")
    
    def bootstrap(self) -> Dict[str, Any]:
        """
        Bootstrap the project from template repository
        
        Returns:
            Dict with bootstrap results and metadata
        """
        
        if not self.config.is_enabled():
            logger.info("ℹ️  Template bootstrap disabled (no TEMPLATE_REPO_URL)")
            return {
                "enabled": False,
                "message": "Template bootstrap disabled"
            }
        
        logger.info("=" * 70)
        logger.info("TEMPLATE BOOTSTRAP")
        logger.info("=" * 70)
        logger.info(f"📦 Template: {self.config.repo_url}")
        logger.info(f"🔀 Ref: {self.config.ref}")
        logger.info(f"📁 Target: {self.project_root}")
        logger.info("=" * 70)
        
        try:
            # Step 1: Clean existing project directory
            self._clean_project_dir()
            
            # Step 2: Clone template repository
            clone_result = self._clone_template()
            
            # Step 3: Checkout specific ref
            checkout_result = self._checkout_ref()
            
            # Step 4: Run init script (optional)
            init_result = None
            if self.config.run_init:
                init_result = self._run_init_script()
            
            # Step 5: Log project structure
            self._log_project_structure()
            
            logger.info("=" * 70)
            logger.info("✅ TEMPLATE BOOTSTRAP COMPLETE")
            logger.info("=" * 70)
            
            return {
                "enabled": True,
                "success": True,
                "repo_url": self.config.repo_url,
                "ref": self.config.ref,
                "project_root": str(self.project_root),
                "clone_result": clone_result,
                "checkout_result": checkout_result,
                "init_result": init_result,
                "files_count": self._count_files()
            }
            
        except Exception as e:
            logger.error(f"❌ Template bootstrap failed: {e}")
            logger.error(f"   Workspace: {self.workspace_root}")
            logger.error(f"   Project: {self.project_root}")
            
            return {
                "enabled": True,
                "success": False,
                "error": str(e),
                "repo_url": self.config.repo_url
            }
    
    def _clean_project_dir(self):
        """Safely remove existing project directory"""
        
        logger.info(f"\n🧹 Cleaning project directory...")
        logger.info(f"   Path: {self.project_root}")
        
        if self.project_root.exists():
            # Safety check: ensure we're cleaning within workspace
            try:
                self.project_root.resolve().relative_to(self.workspace_root.resolve())
            except ValueError:
                raise RuntimeError(
                    f"Safety check failed: {self.project_root} is not within "
                    f"{self.workspace_root}. Refusing to delete."
                )
            
            # Count files before deletion
            file_count = sum(1 for _ in self.project_root.rglob("*") if _.is_file())
            logger.info(f"   Removing {file_count} files...")
            
            # Remove directory
            shutil.rmtree(self.project_root)
            logger.info(f"   ✅ Cleaned successfully")
        else:
            logger.info(f"   ℹ️  Directory does not exist (clean state)")
        
        # Ensure parent directory exists
        self.project_root.parent.mkdir(parents=True, exist_ok=True)
    
    def _clone_template(self) -> Dict[str, Any]:
        """Clone the template repository"""
        
        logger.info(f"\n📥 Cloning template repository...")
        logger.info(f"   URL: {self.config.repo_url}")
        logger.info(f"   Target: {self.project_root}")
        
        # Build git clone command
        cmd = [
            "git", "clone",
            "--depth", "1",  # Shallow clone for speed
            "--single-branch",
            self.config.repo_url,
            str(self.project_root)
        ]
        
        logger.info(f"   Command: {' '.join(cmd)}")
        
        try:
            # Run git clone
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True
            )
            
            logger.info(f"   ✅ Clone successful")
            
            # Log stdout if present
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    logger.debug(f"      {line}")
            
            return {
                "success": True,
                "command": ' '.join(cmd),
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"   ❌ Clone timeout after 5 minutes")
            raise RuntimeError("Git clone timed out after 5 minutes")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"   ❌ Clone failed (exit code {e.returncode})")
            logger.error(f"   stdout: {e.stdout}")
            logger.error(f"   stderr: {e.stderr}")
            raise RuntimeError(f"Git clone failed: {e.stderr}")
        
        except FileNotFoundError:
            logger.error(f"   ❌ git command not found")
            raise RuntimeError("git is not installed or not in PATH")
    
    def _checkout_ref(self) -> Dict[str, Any]:
        """Checkout specific ref (branch, tag, or commit)"""
        
        # If ref is "main" or "master", skip checkout (already on default branch)
        if self.config.ref in ("main", "master"):
            logger.info(f"\n🔀 Ref: {self.config.ref} (default branch, skipping checkout)")
            return {
                "success": True,
                "ref": self.config.ref,
                "skipped": True
            }
        
        logger.info(f"\n🔀 Checking out ref: {self.config.ref}")
        
        cmd = ["git", "checkout", self.config.ref]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            
            logger.info(f"   ✅ Checkout successful")
            
            # Get current commit SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=True
            )
            
            commit_sha = sha_result.stdout.strip()
            logger.info(f"   Commit: {commit_sha[:7]}")
            
            return {
                "success": True,
                "ref": self.config.ref,
                "commit_sha": commit_sha,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"   ❌ Checkout failed (exit code {e.returncode})")
            logger.error(f"   stderr: {e.stderr}")
            raise RuntimeError(f"Git checkout failed: {e.stderr}")
    
    def _run_init_script(self) -> Optional[Dict[str, Any]]:
        """Run template init script if present"""
        
        logger.info(f"\n🔧 Looking for init script...")
        
        # Look for common init script names
        init_scripts = [
            "init.sh",
            "bootstrap.sh",
            "setup.sh",
            ".init.sh"
        ]
        
        init_script = None
        for script_name in init_scripts:
            candidate = self.project_root / script_name
            if candidate.exists() and candidate.is_file():
                init_script = candidate
                logger.info(f"   Found: {script_name}")
                break
        
        if not init_script:
            logger.info(f"   ℹ️  No init script found (looked for: {', '.join(init_scripts)})")
            return None
        
        logger.info(f"   Running: {init_script.name}")
        
        # Make script executable
        init_script.chmod(0o755)
        
        try:
            result = subprocess.run(
                [str(init_script)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True
            )
            
            logger.info(f"   ✅ Init script completed successfully")
            
            # Log output
            if result.stdout:
                for line in result.stdout.strip().split('\n')[:10]:  # First 10 lines
                    logger.info(f"      {line}")
            
            return {
                "success": True,
                "script": init_script.name,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            logger.warning(f"   ⚠️  Init script timeout after 5 minutes")
            return {
                "success": False,
                "error": "Timeout after 5 minutes"
            }
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"   ⚠️  Init script failed (exit code {e.returncode})")
            logger.warning(f"   stderr: {e.stderr}")
            return {
                "success": False,
                "error": str(e),
                "stdout": e.stdout,
                "stderr": e.stderr
            }
    
    def _log_project_structure(self):
        """Log project directory structure"""
        
        logger.info(f"\n📂 Project structure:")
        
        if not self.project_root.exists():
            logger.warning(f"   ⚠️  Project directory does not exist")
            return
        
        # Count files and directories
        files = list(self.project_root.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        dir_count = sum(1 for f in files if f.is_dir())
        
        logger.info(f"   Files: {file_count}")
        logger.info(f"   Directories: {dir_count}")
        
        # List top-level items
        logger.info(f"\n   Top-level items:")
        top_level = sorted(self.project_root.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        
        for item in top_level[:20]:  # Show first 20 items
            if item.name.startswith('.git'):
                continue  # Skip .git directory
            
            prefix = "📁" if item.is_dir() else "📄"
            logger.info(f"   {prefix} {item.name}")
        
        if len(top_level) > 20:
            logger.info(f"   ... and {len(top_level) - 20} more items")
    
    def _count_files(self) -> int:
        """Count files in project directory"""
        if not self.project_root.exists():
            return 0
        return sum(1 for _ in self.project_root.rglob("*") if _.is_file())
    
    def publish_to_site(self, site_root: Path) -> Dict[str, Any]:
        """
        Copy project output to SITE_ROOT
        
        Args:
            site_root: Path to SITE_ROOT directory
        
        Returns:
            Dict with publish results
        """
        
        if not self.config.publish_to_site:
            return {
                "enabled": False,
                "message": "PUBLISH_TO_SITE is disabled"
            }
        
        logger.info(f"\n📋 Publishing to SITE_ROOT...")
        logger.info(f"   Source: {self.project_root}")
        logger.info(f"   Target: {site_root}")
        
        site_root = Path(site_root)
        site_root.mkdir(parents=True, exist_ok=True)
        
        try:
            # Copy all files from PROJECT_ROOT to SITE_ROOT
            files_copied = 0
            
            for item in self.project_root.rglob("*"):
                # Skip .git directory
                if ".git" in item.parts:
                    continue
                
                if item.is_file():
                    rel_path = item.relative_to(self.project_root)
                    dest = site_root / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    files_copied += 1
            
            logger.info(f"   ✅ Published {files_copied} files")
            
            return {
                "enabled": True,
                "success": True,
                "files_copied": files_copied,
                "source": str(self.project_root),
                "target": str(site_root)
            }
            
        except Exception as e:
            logger.error(f"   ❌ Publish failed: {e}")
            return {
                "enabled": True,
                "success": False,
                "error": str(e)
            }


def bootstrap_from_template(workspace_root: Path, config: Optional[TemplateConfig] = None) -> Dict[str, Any]:
    """
    Bootstrap project from template repository
    
    Args:
        workspace_root: Path to workspace root directory
        config: Optional template configuration (defaults to env vars)
    
    Returns:
        Dict with bootstrap results
    """
    
    if config is None:
        config = TemplateConfig.from_env()
    
    bootstrap = TemplateBootstrap(workspace_root, config)
    return bootstrap.bootstrap()
