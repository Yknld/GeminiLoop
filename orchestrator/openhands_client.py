"""
OpenHands Client

Integration layer for applying code patches via OpenHands.
Supports both local subprocess and mock implementations.
"""

import os
import json
import subprocess
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class OpenHandsClient(ABC):
    """
    Base interface for OpenHands integration
    
    Implementations can use actual OpenHands CLI or mock for testing
    """
    
    @abstractmethod
    def apply_patch_plan(self, workspace_path: str, patch_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a patch plan to the workspace
        
        Args:
            workspace_path: Path to workspace directory
            patch_plan: Patch plan dict with:
                {
                    "files": [
                        {
                            "path": "index.html",
                            "action": "modify",  # or "create", "delete"
                            "description": "Fix button styling",
                            "changes": [...]  # Optional: specific changes
                        }
                    ],
                    "instructions": "High-level instructions for OpenHands"
                }
        
        Returns:
            Result dict with:
                {
                    "success": bool,
                    "files_modified": List[str],
                    "stdout": str,
                    "stderr": str,
                    "duration_seconds": float
                }
        """
        pass


class LocalSubprocessOpenHandsClient(OpenHandsClient):
    """
    OpenHands client that runs openhands CLI as subprocess
    
    Runs in the same container, writes logs to artifacts
    """
    
    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path.cwd() / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if openhands CLI is available
        try:
            result = subprocess.run(
                ["which", "openhands"],
                capture_output=True,
                text=True
            )
            self.openhands_available = result.returncode == 0
            self.openhands_path = result.stdout.strip() if self.openhands_available else None
        except Exception as e:
            logger.warning(f"Could not check for openhands: {e}")
            self.openhands_available = False
            self.openhands_path = None
        
        if not self.openhands_available:
            logger.warning("OpenHands CLI not found. Install with: pip install openhands")
    
    def apply_patch_plan(self, workspace_path: str, patch_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch plan using OpenHands CLI"""
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands CLI not available. Set OPENHANDS_MODE=mock to use fallback.")
        
        workspace_path = Path(workspace_path)
        start_time = datetime.now()
        
        logger.info(f"🔧 Applying patch plan via OpenHands CLI")
        logger.info(f"   Workspace: {workspace_path}")
        
        # Build instructions for OpenHands
        instructions = self._build_instructions(patch_plan)
        
        # Write instructions to temp file
        instructions_file = self.artifacts_dir / f"openhands_instructions_{int(start_time.timestamp())}.txt"
        instructions_file.write_text(instructions)
        
        logger.info(f"   Instructions: {instructions_file}")
        
        # Run openhands CLI
        # Note: This is a placeholder - actual OpenHands API may differ
        # You'll need to adjust based on OpenHands CLI interface
        try:
            cmd = [
                "openhands",
                "run",
                "--workspace", str(workspace_path),
                "--instructions", str(instructions_file),
                "--no-interactive"
            ]
            
            logger.info(f"   Command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Save logs
            stdout_file = self.artifacts_dir / f"openhands_stdout_{int(start_time.timestamp())}.log"
            stderr_file = self.artifacts_dir / f"openhands_stderr_{int(start_time.timestamp())}.log"
            
            stdout_file.write_text(result.stdout)
            stderr_file.write_text(result.stderr)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            success = result.returncode == 0
            
            logger.info(f"   OpenHands completed: {'✅ success' if success else '❌ failed'}")
            logger.info(f"   Duration: {duration:.2f}s")
            
            # Determine which files were modified
            files_modified = self._detect_modified_files(workspace_path, patch_plan)
            
            return {
                "success": success,
                "files_modified": files_modified,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": duration,
                "stdout_log": str(stdout_file),
                "stderr_log": str(stderr_file)
            }
            
        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"   OpenHands timed out after {duration:.2f}s")
            
            return {
                "success": False,
                "files_modified": [],
                "stdout": "",
                "stderr": "Process timed out",
                "duration_seconds": duration
            }
        
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"   OpenHands error: {e}")
            
            return {
                "success": False,
                "files_modified": [],
                "stdout": "",
                "stderr": str(e),
                "duration_seconds": duration
            }
    
    def _build_instructions(self, patch_plan: Dict[str, Any]) -> str:
        """Build instructions string for OpenHands"""
        
        instructions = patch_plan.get("instructions", "Apply the following changes:")
        instructions += "\n\n"
        
        for file_change in patch_plan.get("files", []):
            path = file_change.get("path")
            action = file_change.get("action", "modify")
            description = file_change.get("description", "")
            
            instructions += f"File: {path}\n"
            instructions += f"Action: {action}\n"
            instructions += f"Description: {description}\n"
            
            if "changes" in file_change:
                instructions += "Changes:\n"
                for change in file_change["changes"]:
                    instructions += f"  - {change}\n"
            
            instructions += "\n"
        
        return instructions
    
    def _detect_modified_files(self, workspace_path: Path, patch_plan: Dict[str, Any]) -> List[str]:
        """Detect which files were actually modified"""
        
        # Simple implementation: return files from patch plan
        # In production, could use git diff or file timestamps
        return [
            f.get("path") 
            for f in patch_plan.get("files", [])
            if f.get("action") in ["modify", "create"]
        ]


class MockOpenHandsClient(OpenHandsClient):
    """
    Mock OpenHands client for testing/demo
    
    Uses simple regex-based edits and string replacements
    """
    
    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path.cwd() / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🎭 Using MockOpenHandsClient (regex-based edits)")
    
    def apply_patch_plan(self, workspace_path: str, patch_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch plan using mock regex-based edits"""
        
        workspace_path = Path(workspace_path)
        start_time = datetime.now()
        
        logger.info(f"🎭 Applying patch plan via Mock OpenHands")
        logger.info(f"   Workspace: {workspace_path}")
        
        files_modified = []
        stdout_lines = []
        stderr_lines = []
        
        try:
            for file_change in patch_plan.get("files", []):
                path = file_change.get("path")
                action = file_change.get("action", "modify")
                description = file_change.get("description", "")
                
                file_path = workspace_path / path
                
                stdout_lines.append(f"Processing: {path}")
                stdout_lines.append(f"  Action: {action}")
                stdout_lines.append(f"  Description: {description}")
                
                if action == "modify" and file_path.exists():
                    # Apply modifications
                    original_content = file_path.read_text()
                    modified_content = self._apply_mock_modifications(
                        original_content, 
                        file_change,
                        description
                    )
                    
                    if modified_content != original_content:
                        # Backup original
                        backup_path = self.artifacts_dir / f"{path}.backup"
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        backup_path.write_text(original_content)
                        
                        # Write modified
                        file_path.write_text(modified_content)
                        files_modified.append(path)
                        
                        stdout_lines.append(f"  ✅ Modified {path}")
                        stdout_lines.append(f"  Backup saved to: {backup_path}")
                    else:
                        stdout_lines.append(f"  ℹ️  No changes needed for {path}")
                
                elif action == "create":
                    # Create new file with default content
                    content = file_change.get("content", self._generate_default_content(path, description))
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content)
                    files_modified.append(path)
                    stdout_lines.append(f"  ✅ Created {path}")
                
                elif action == "delete" and file_path.exists():
                    # Delete file (with backup)
                    backup_path = self.artifacts_dir / f"{path}.deleted"
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.write_text(file_path.read_text())
                    file_path.unlink()
                    files_modified.append(path)
                    stdout_lines.append(f"  ✅ Deleted {path}")
                
                else:
                    stderr_lines.append(f"  ⚠️  Could not apply action '{action}' to {path}")
                
                stdout_lines.append("")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            stdout = "\n".join(stdout_lines)
            stderr = "\n".join(stderr_lines)
            
            # Save logs
            log_file = self.artifacts_dir / f"mock_openhands_{int(start_time.timestamp())}.log"
            log_file.write_text(f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}")
            
            logger.info(f"   Mock OpenHands completed: ✅")
            logger.info(f"   Files modified: {len(files_modified)}")
            logger.info(f"   Duration: {duration:.2f}s")
            
            return {
                "success": True,
                "files_modified": files_modified,
                "stdout": stdout,
                "stderr": stderr,
                "duration_seconds": duration,
                "log_file": str(log_file)
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"   Mock OpenHands error: {e}")
            
            return {
                "success": False,
                "files_modified": files_modified,
                "stdout": "\n".join(stdout_lines),
                "stderr": str(e),
                "duration_seconds": duration
            }
    
    def _apply_mock_modifications(
        self, 
        content: str, 
        file_change: Dict[str, Any],
        description: str
    ) -> str:
        """Apply mock modifications using simple regex patterns"""
        
        modified = content
        
        # Extract specific changes if provided
        changes = file_change.get("changes", [])
        
        if changes:
            # Apply each change
            for change in changes:
                if isinstance(change, dict):
                    # Structured change with find/replace
                    find = change.get("find", "")
                    replace = change.get("replace", "")
                    if find and replace:
                        modified = modified.replace(find, replace)
                elif isinstance(change, str):
                    # Parse natural language change (best effort)
                    modified = self._apply_natural_language_change(modified, change)
        else:
            # Apply generic improvements based on description
            modified = self._apply_generic_improvements(modified, description)
        
        return modified
    
    def _apply_natural_language_change(self, content: str, change_description: str) -> str:
        """Apply changes based on natural language description (best effort)"""
        
        # Simple pattern matching for common changes
        lower_desc = change_description.lower()
        
        # Color changes
        if "color" in lower_desc or "colour" in lower_desc:
            # Try to extract color and apply it
            if "blue" in lower_desc:
                content = re.sub(r'color:\s*#?\w+', 'color: #667eea', content)
            elif "red" in lower_desc:
                content = re.sub(r'color:\s*#?\w+', 'color: #e53e3e', content)
            elif "green" in lower_desc:
                content = re.sub(r'color:\s*#?\w+', 'color: #48bb78', content)
        
        # Font size changes
        if "font" in lower_desc and "size" in lower_desc:
            if "larger" in lower_desc or "bigger" in lower_desc:
                content = re.sub(r'font-size:\s*\d+px', lambda m: f'font-size: {int(m.group(0).split(":")[1].strip().replace("px","")) + 4}px', content)
        
        # Padding/margin changes
        if "padding" in lower_desc:
            if "more" in lower_desc or "increase" in lower_desc:
                content = re.sub(r'padding:\s*\d+px', lambda m: f'padding: {int(m.group(0).split(":")[1].strip().replace("px","")) + 8}px', content)
        
        # Button styling
        if "button" in lower_desc and "style" in lower_desc:
            # Add button styling if not present
            if "button {" not in content:
                style_section = content.find("</style>")
                if style_section != -1:
                    button_style = """
        button {
            padding: 12px 24px;
            border-radius: 6px;
            border: none;
            background: #667eea;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        button:hover {
            background: #5568d3;
            transform: translateY(-2px);
        }
        """
                    content = content[:style_section] + button_style + content[style_section:]
        
        return content
    
    def _apply_generic_improvements(self, content: str, description: str) -> str:
        """Apply generic improvements based on description"""
        
        lower_desc = description.lower()
        
        # Improve styling if mentioned
        if "style" in lower_desc or "design" in lower_desc or "visual" in lower_desc:
            # Add some modern styling improvements
            if "transition" not in content:
                # Add transitions to interactive elements
                style_section = content.find("</style>")
                if style_section != -1:
                    improvements = """
        * {
            transition: all 0.3s ease;
        }
        """
                    content = content[:style_section] + improvements + content[style_section:]
        
        # Fix errors if mentioned
        if "error" in lower_desc or "bug" in lower_desc or "fix" in lower_desc:
            # Try to fix common issues
            # Fix unclosed tags
            if content.count("<div>") > content.count("</div>"):
                content += "\n</div>"
            if content.count("<button>") > content.count("</button>"):
                content += "\n</button>"
        
        return content
    
    def _generate_default_content(self, path: str, description: str) -> str:
        """Generate default content for new files"""
        
        if path.endswith(".html"):
            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated File</title>
</head>
<body>
    <h1>New File</h1>
    <p>{description}</p>
</body>
</html>
"""
        elif path.endswith(".css"):
            return f"""/* {description} */
body {{
    font-family: sans-serif;
    padding: 20px;
}}
"""
        elif path.endswith(".js"):
            return f"""// {description}
console.log('Generated file');
"""
        else:
            return f"# {description}\n"


def get_openhands_client(artifacts_dir: Optional[Path] = None) -> OpenHandsClient:
    """
    Factory function to get appropriate OpenHands client
    
    Based on OPENHANDS_MODE environment variable:
    - "local": LocalSubprocessOpenHandsClient
    - "mock": MockOpenHandsClient (default)
    """
    
    mode = os.getenv("OPENHANDS_MODE", "mock").lower()
    
    logger.info(f"🔧 Initializing OpenHands client: mode={mode}")
    
    if mode == "local":
        return LocalSubprocessOpenHandsClient(artifacts_dir)
    elif mode == "mock":
        return MockOpenHandsClient(artifacts_dir)
    else:
        logger.warning(f"Unknown OPENHANDS_MODE: {mode}, defaulting to mock")
        return MockOpenHandsClient(artifacts_dir)
