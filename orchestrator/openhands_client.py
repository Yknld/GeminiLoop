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
import traceback
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
    def generate_code(self, task: str, workspace_path: str, detailed_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate initial code from scratch using OpenHands
        
        Args:
            task: User's task description
            workspace_path: Path to workspace directory
            detailed_requirements: Detailed requirements including:
                {
                    "task": "Create a quiz",
                    "functionality": ["submit button", "score display", ...],
                    "styling": ["good contrast", "responsive", ...],
                    "accessibility": ["ARIA labels", "keyboard nav", ...],
                    "technical": ["vanilla JS", "self-contained", ...]
                }
        
        Returns:
            Result dict with files generated and any diffs
        """
        pass
    
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
                    "diffs": List[Dict],  # Before/after diffs
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
        
        # Create diffs directory
        self.diffs_dir = self.artifacts_dir / "diffs"
        self.diffs_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if OpenHands SDK is available
        self.openhands_available = False
        
        try:
            # Try importing OpenHands SDK
            import openhands.sdk
            self.openhands_available = True
            logger.info("✅ OpenHands SDK found and imported successfully")
        except ImportError as e:
            logger.error("❌ OpenHands SDK not found")
            logger.error(f"   Import error: {e}")
            logger.error("   Install with: pip install openhands-sdk openhands-tools openhands-workspace")
    
    def generate_code(self, task: str, workspace_path: str, detailed_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate initial code using OpenHands Python SDK"""
        
        start_time = datetime.now()
        workspace_path = Path(workspace_path)
        
        logger.info(f"🎨 OpenHands SDK: Generating code from scratch")
        logger.info(f"   Task: {task}")
        logger.info(f"   Workspace: {workspace_path}")
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands not available. Cannot generate code without OpenHands.")
        
        # Build detailed prompt for OpenHands
        prompt = self._build_generation_prompt(task, detailed_requirements)
        
        # Save prompt for debugging
        prompt_file = self.artifacts_dir / f"generation_prompt_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        prompt_file.write_text(prompt)
        logger.info(f"   Prompt saved: {prompt_file}")
        
        # Run OpenHands via Python SDK
        try:
            # Import OpenHands SDK
            from openhands.sdk import LLM, Agent, Conversation, Tool
            from openhands.tools.browser_use import BrowserToolSet
            from openhands.tools.file_editor import FileEditorTool
            from openhands.tools.terminal import TerminalTool
            from pydantic import SecretStr
            
            # Capture before state
            before_files = self._capture_workspace_state(workspace_path)
            
            # Configure LLM (using Gemini AI Studio, not Vertex AI)
            # Use "gemini/" prefix to force LiteLLM to use AI Studio instead of Vertex
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            if not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            llm = LLM(
                model=model,
                api_key=SecretStr(os.getenv("GOOGLE_AI_STUDIO_API_KEY")),
            )
            
            # Create agent with browser, file, and terminal tools
            agent = Agent(
                llm=llm,
                tools=[
                    Tool(name=BrowserToolSet.name),
                    Tool(name=FileEditorTool.name),
                    Tool(name=TerminalTool.name),
                ]
            )
            
            # Create conversation
            conversation = Conversation(agent=agent, workspace=str(workspace_path))
            
            # Send task and run
            logger.info("   Sending task to OpenHands agent...")
            conversation.send_message(prompt)
            conversation.run()
            
            # Capture after state
            after_files = self._capture_workspace_state(workspace_path)
            
            # Generate diffs
            diffs = self._generate_diffs(before_files, after_files, "generation")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ OpenHands SDK completed in {duration:.2f}s")
            
            return {
                "success": True,
                "error": None,
                "files_generated": list(after_files.keys()),
                "diffs": diffs,
                "stdout": "OpenHands SDK execution completed",
                "stderr": "",
                "duration_seconds": duration,
                "prompt_file": str(prompt_file)
            }
            
        except Exception as e:
            logger.error(f"OpenHands SDK failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "stdout": "",
                "stderr": str(e)
            }
    
    def apply_patch_plan(self, workspace_path: str, patch_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch plan using OpenHands CLI"""
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands CLI not available. Cannot apply patches without OpenHands.")
        
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
        try:
            # Build command with detected CLI
            # OpenHands CLI format: openhands COMMAND [args]
            cmd = self.openhands_command + [
                "patch",
                instructions
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
    
    def _capture_workspace_state(self, workspace_path: Path) -> Dict[str, str]:
        """Capture current state of all files in workspace"""
        
        files_state = {}
        
        if not workspace_path.exists():
            return files_state
        
        for file_path in workspace_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                try:
                    relative_path = file_path.relative_to(workspace_path)
                    content = file_path.read_text()
                    files_state[str(relative_path)] = content
                except:
                    pass  # Skip files that can't be read
        
        return files_state
    
    def _generate_diffs(self, before: Dict[str, str], after: Dict[str, str], operation: str) -> List[Dict]:
        """Generate diffs between before and after states"""
        
        diffs = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # New files
        for filepath, content in after.items():
            if filepath not in before:
                diff_file = self.diffs_dir / f"{operation}_{timestamp}_{filepath.replace('/', '_')}.diff"
                diff_content = f"NEW FILE: {filepath}\n\n{content}"
                diff_file.write_text(diff_content)
                
                diffs.append({
                    "file": filepath,
                    "type": "created",
                    "diff_file": str(diff_file),
                    "lines_added": len(content.split('\n'))
                })
        
        # Modified files
        for filepath, new_content in after.items():
            if filepath in before:
                old_content = before[filepath]
                if old_content != new_content:
                    # Generate unified diff
                    import difflib
                    diff_lines = list(difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        new_content.splitlines(keepends=True),
                        fromfile=f"a/{filepath}",
                        tofile=f"b/{filepath}",
                        lineterm=''
                    ))
                    
                    if diff_lines:
                        diff_file = self.diffs_dir / f"{operation}_{timestamp}_{filepath.replace('/', '_')}.diff"
                        diff_file.write_text(''.join(diff_lines))
                        
                        diffs.append({
                            "file": filepath,
                            "type": "modified",
                            "diff_file": str(diff_file),
                            "lines_added": len([l for l in diff_lines if l.startswith('+') and not l.startswith('+++')]),
                            "lines_removed": len([l for l in diff_lines if l.startswith('-') and not l.startswith('---')])
                        })
        
        # Deleted files
        for filepath in before:
            if filepath not in after:
                diffs.append({
                    "file": filepath,
                    "type": "deleted",
                    "lines_removed": len(before[filepath].split('\n'))
                })
        
        return diffs
    
    def _build_generation_prompt(self, task: str, requirements: Dict[str, Any]) -> str:
        """Build extremely detailed prompt for OpenHands code generation"""
        
        prompt = f"""TASK: Generate complete, production-ready HTML page for: {task}

CRITICAL REQUIREMENTS:

1. FUNCTIONALITY (MUST BE FULLY WORKING):
   - ALL interactive elements MUST be functional (buttons, forms, inputs, etc.)
   - Implement complete JavaScript for ALL user interactions
   - Add event handlers for every clickable element
   - Form validation with clear error messages
   - NO non-functional UI elements
   - Test all interactions before completing

2. STYLING & VISUAL DESIGN:
   - Modern, professional appearance
   - Color palette:
     * Primary: #667eea (purple-blue)
     * Success: #48bb78 (green)
     * Warning: #f59e0b (orange)
     * Error: #e53e3e (red)
     * Text: #2d3748 (dark gray)
     * Background: #f7fafc (light gray)
   - Typography:
     * Headings: 24-32px, font-weight: 600-700
     * Body: 16px, line-height: 1.6
     * Buttons: 14-16px, font-weight: 500
   - Spacing (8px grid):
     * Small: 8px
     * Medium: 16px
     * Large: 24px
     * XL: 32px
     * XXL: 40px
   - Shadows for depth:
     * Cards: 0 2px 8px rgba(0,0,0,0.1)
     * Buttons: 0 2px 4px rgba(0,0,0,0.1)
   - Border radius: 6-8px for modern look
   - Smooth transitions: all 0.3s ease

3. RESPONSIVE DESIGN (CRITICAL):
   - Mobile-first approach
   - Breakpoints:
     * Mobile: < 640px
     * Tablet: 640px - 1024px
     * Desktop: > 1024px
   - Flexible layouts with flexbox/grid
   - Touch-friendly tap targets (min 44px)
   - Responsive typography (scale down on mobile)
   - Test at 375px (mobile) and 1440px (desktop)

4. ACCESSIBILITY (WCAG AA):
   - Semantic HTML5 elements
   - All images have alt text
   - Form labels properly associated
   - Color contrast ratio ≥ 4.5:1
   - Keyboard navigation support
   - Focus indicators visible
   - ARIA labels where needed
   - Skip to content links

5. CODE QUALITY:
   - Clean, readable, well-commented code
   - Consistent indentation (2 spaces)
   - Descriptive variable/function names
   - No console.log() in production
   - Minify for production
   - Cross-browser compatible

6. USER EXPERIENCE:
   - Loading states for async operations
   - Clear feedback for all actions
   - Error handling with helpful messages
   - Success confirmation messages
   - Smooth animations and transitions
   - Intuitive navigation
   - Clear visual hierarchy

SPECIFIC REQUIREMENTS FROM USER:
"""
        
        # Add specific requirements if provided
        if requirements:
            if "functionality" in requirements:
                prompt += f"\nFunctionality:\n"
                for req in requirements["functionality"]:
                    prompt += f"  - {req}\n"
            
            if "styling" in requirements:
                prompt += f"\nStyling:\n"
                for req in requirements["styling"]:
                    prompt += f"  - {req}\n"
            
            if "responsive" in requirements:
                prompt += f"\nResponsive:\n"
                for req in requirements["responsive"]:
                    prompt += f"  - {req}\n"
            
            if "accessibility" in requirements:
                prompt += f"\nAccessibility:\n"
                for req in requirements["accessibility"]:
                    prompt += f"  - {req}\n"
            
            if "technical" in requirements:
                prompt += f"\nTechnical:\n"
                for req in requirements["technical"]:
                    prompt += f"  - {req}\n"
        
        prompt += """

DELIVERABLES:
- Single HTML file (index.html) with embedded CSS and JavaScript
- All functionality working
- Mobile and desktop responsive
- Accessible (WCAG AA)
- Production-ready code

Generate the complete, working HTML file now. Make it professional and production-ready.
"""
        
        return prompt
    


class MockOpenHandsClient(OpenHandsClient):
    """
    Mock OpenHands client for testing/demo
    
    Uses simple regex-based edits and string replacements
    """
    
    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path.cwd() / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🎭 Using MockOpenHandsClient (regex-based edits)")
    
    def generate_code(self, task: str, workspace_path: str, detailed_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Mock code generation - creates basic template"""
        
        logger.info("🎭 Mock generation - creating basic template")
        
        # Use LocalSubprocessOpenHandsClient's fallback
        workspace_path = Path(workspace_path)
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{task}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{task}</h1>
        <p>Mock generated content</p>
    </div>
</body>
</html>"""
        
        filepath = workspace_path / "index.html"
        filepath.write_text(html_content)
        
        return {
            "success": True,
            "files_generated": ["index.html"],
            "diffs": [],
            "stdout": "Mock template created",
            "stderr": "",
            "duration_seconds": 0.1
        }
    
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
