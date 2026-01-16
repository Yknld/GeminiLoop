"""
Path Configuration - Single Source of Truth

Centralizes all directory paths and file operations for GeminiLoop on RunPod.
Prevents path confusion between /workspace, /site, and project directories.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PathConfig:
    """
    Canonical directory configuration for OpenHands/RunPod deployment
    
    This is the SINGLE SOURCE OF TRUTH for all file paths in the system.
    """
    
    # Root workspace directory (OpenHands runtime environment)
    workspace_root: Path
    
    # Project root - where agent reads/writes files (relative to workspace_root)
    project_root: Path
    
    # Site directory for OpenHands evaluator (if it requires /site)
    site_root: Optional[Path] = None
    
    # Preview server configuration
    preview_host: str = "127.0.0.1"
    preview_port: int = 8000
    
    def __post_init__(self):
        """Ensure all paths are Path objects"""
        if isinstance(self.workspace_root, str):
            self.workspace_root = Path(self.workspace_root)
        if isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)
        if self.site_root and isinstance(self.site_root, str):
            self.site_root = Path(self.site_root)
    
    @property
    def preview_url(self) -> str:
        """Get the canonical HTTP preview URL (never use file://)"""
        return f"http://{self.preview_host}:{self.preview_port}/"
    
    def validate_path_in_project(self, path: Path) -> bool:
        """
        Validate that a path is within PROJECT_ROOT
        
        This is a guardrail to prevent writing outside the project directory.
        """
        try:
            path = Path(path).resolve()
            project = self.project_root.resolve()
            return path.is_relative_to(project)
        except (ValueError, RuntimeError):
            return False
    
    def safe_path_join(self, *parts: str) -> Path:
        """
        Safely join path parts relative to PROJECT_ROOT
        
        Raises ValueError if the result would be outside PROJECT_ROOT.
        """
        result = self.project_root.joinpath(*parts).resolve()
        if not self.validate_path_in_project(result):
            raise ValueError(
                f"Path '{result}' is outside PROJECT_ROOT '{self.project_root}'. "
                "This is not allowed for security."
            )
        return result
    
    def ensure_directories(self):
        """Create all required directories"""
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.project_root.mkdir(parents=True, exist_ok=True)
        if self.site_root:
            self.site_root.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ Directories ensured:")
        logger.info(f"   WORKSPACE_ROOT: {self.workspace_root}")
        logger.info(f"   PROJECT_ROOT: {self.project_root}")
        if self.site_root:
            logger.info(f"   SITE_ROOT: {self.site_root}")
    
    def log_startup_info(self):
        """Log comprehensive startup information for debugging"""
        import subprocess
        
        logger.info("=" * 70)
        logger.info("PATH CONFIGURATION - SINGLE SOURCE OF TRUTH")
        logger.info("=" * 70)
        
        # Directory paths
        logger.info("\n📁 Directory Configuration:")
        logger.info(f"   WORKSPACE_ROOT: {self.workspace_root}")
        logger.info(f"   PROJECT_ROOT: {self.project_root}")
        if self.site_root:
            logger.info(f"   SITE_ROOT: {self.site_root}")
        else:
            logger.info(f"   SITE_ROOT: (not used)")
        
        # Preview server
        logger.info("\n🌐 Preview Server:")
        logger.info(f"   Host: {self.preview_host}")
        logger.info(f"   Port: {self.preview_port}")
        logger.info(f"   URL: {self.preview_url}")
        
        # Current working directory
        try:
            cwd = Path.cwd()
            logger.info(f"\n📍 Current Working Directory:")
            logger.info(f"   pwd: {cwd}")
        except Exception as e:
            logger.warning(f"   Could not get pwd: {e}")
        
        # List key directories
        for name, path in [
            ("WORKSPACE_ROOT", self.workspace_root),
            ("PROJECT_ROOT", self.project_root),
            ("SITE_ROOT", self.site_root)
        ]:
            if path and path.exists():
                try:
                    items = list(path.iterdir())
                    logger.info(f"\n📂 Contents of {name} ({path}):")
                    if items:
                        for item in items[:10]:  # Show first 10 items
                            prefix = "📁" if item.is_dir() else "📄"
                            logger.info(f"   {prefix} {item.name}")
                        if len(items) > 10:
                            logger.info(f"   ... and {len(items) - 10} more items")
                    else:
                        logger.info(f"   (empty)")
                except Exception as e:
                    logger.warning(f"   Could not list {name}: {e}")
        
        logger.info("\n" + "=" * 70)


def detect_workspace_root() -> Path:
    """
    Detect the OpenHands workspace root directory
    
    Priority:
    1. WORKSPACE_ROOT environment variable (explicit override)
    2. OpenHands runtime directory (if running in OpenHands)
    3. Current working directory (fallback)
    """
    
    # Check explicit environment override
    if "WORKSPACE_ROOT" in os.environ:
        workspace = Path(os.environ["WORKSPACE_ROOT"])
        logger.info(f"Using WORKSPACE_ROOT from environment: {workspace}")
        return workspace
    
    # Check OpenHands runtime directory
    # OpenHands typically uses /workspace or similar
    openhands_dirs = [
        Path("/workspace"),
        Path("/root/workspace"),
        Path.home() / "workspace"
    ]
    
    for candidate in openhands_dirs:
        if candidate.exists():
            logger.info(f"Detected OpenHands workspace: {candidate}")
            return candidate
    
    # Fallback to current directory
    cwd = Path.cwd()
    logger.info(f"Using current directory as workspace root: {cwd}")
    return cwd


def create_path_config(base_dir: Optional[Path] = None, project_dir_name: Optional[str] = None) -> PathConfig:
    """
    Create canonical path configuration
    
    This is the factory function that establishes the single source of truth
    for all paths in the system.
    
    Args:
        base_dir: Optional base directory override (for testing)
        project_dir_name: Optional project directory name (default: "project")
    
    Returns:
        PathConfig with all canonical paths configured
    """
    
    # Detect workspace root
    if base_dir:
        workspace_root = Path(base_dir)
    else:
        workspace_root = detect_workspace_root()
    
    # Project root is always a subdirectory of workspace
    # Use PROJECT_DIR_NAME from env if not provided
    if project_dir_name is None:
        project_dir_name = os.getenv("PROJECT_DIR_NAME", "project")
    
    project_root = workspace_root / project_dir_name
    
    # Site root (for OpenHands evaluator compatibility)
    # Only create if evaluator explicitly needs it
    site_root = workspace_root / "site"
    
    # Preview server configuration
    preview_host = os.getenv("PREVIEW_HOST", "127.0.0.1")
    preview_port = int(os.getenv("PREVIEW_PORT", "8000"))
    
    config = PathConfig(
        workspace_root=workspace_root,
        project_root=project_root,
        site_root=site_root,
        preview_host=preview_host,
        preview_port=preview_port
    )
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Log startup information
    config.log_startup_info()
    
    return config


# Global instance (lazy-loaded)
_path_config: Optional[PathConfig] = None


def get_path_config(base_dir: Optional[Path] = None) -> PathConfig:
    """
    Get the global path configuration singleton
    
    This ensures all parts of the system use the same path configuration.
    """
    global _path_config
    
    if _path_config is None:
        _path_config = create_path_config(base_dir)
    
    return _path_config


def reset_path_config():
    """Reset the global path configuration (for testing)"""
    global _path_config
    _path_config = None
