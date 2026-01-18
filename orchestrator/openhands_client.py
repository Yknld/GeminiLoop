"""
OpenHands Client

Integration layer for applying code patches via OpenHands.
Supports both local subprocess and mock implementations.

IMPORTANT: All file operations are restricted to PROJECT_ROOT for security.
Use paths module to ensure operations stay within allowed directories.
"""

import os
import json
import subprocess
import logging
import re
import traceback
import threading
import signal
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
    
    def generate_code(self, task: str, workspace_path: str, detailed_requirements: Dict[str, Any] = None, template_file: str = None) -> Dict[str, Any]:
        """Generate initial code using OpenHands Python SDK, optionally starting from template"""
        
        start_time = datetime.now()
        workspace_path = Path(workspace_path)
        
        if template_file and Path(template_file).exists():
            logger.info(f"🎨 OpenHands SDK: Populating template with content")
            logger.info(f"   Template: {template_file}")
        else:
            logger.info(f"🎨 OpenHands SDK: Generating code from scratch")
        logger.info(f"   Task: {task}")
        logger.info(f"   Workspace: {workspace_path}")
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands not available. Cannot generate code without OpenHands.")
        
        # Build detailed prompt for OpenHands
        prompt = self._build_generation_prompt(task, detailed_requirements, template_file, workspace_path)
        
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
            model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
            if not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            llm = LLM(
                model=model,
                api_key=SecretStr(os.getenv("GOOGLE_AI_STUDIO_API_KEY")),
            )
            
            # Create agent with browser, file, and terminal tools
            # Disable auto-screenshots to prevent context overflow
            agent = Agent(
                llm=llm,
                tools=[
                    Tool(name=BrowserToolSet.name, params={"include_screenshot": False}),
                    Tool(name=FileEditorTool.name),
                    Tool(name=TerminalTool.name),
                ]
            )
            
            # Ensure workspace path is absolute and valid
            workspace_path_abs = workspace_path.resolve()
            logger.info(f"   OpenHands workspace: {workspace_path_abs}")
            
            # Create conversation with absolute workspace path
            conversation = Conversation(agent=agent, workspace=str(workspace_path_abs))
            
            # Send task and run
            logger.info("   Sending task to OpenHands agent...")
            logger.info(f"   Task length: {len(prompt)} characters")
            logger.info(f"   Before state: {len(before_files)} files")
            if before_files:
                logger.info(f"   Before files: {list(before_files.keys())[:5]}")
            
            conversation.send_message(prompt)
            
            # Run with timeout (default 10 minutes, configurable via env var)
            timeout_seconds = float(os.getenv('OPENHANDS_TIMEOUT_SECONDS', '600'))  # 10 minutes default
            
            # Use threading to implement timeout for blocking call
            run_complete = threading.Event()
            run_exception = [None]
            
            def run_conversation():
                try:
                    conversation.run()
                    run_complete.set()
                except Exception as e:
                    run_exception[0] = e
                    run_complete.set()
            
            # Start conversation in separate thread
            run_thread = threading.Thread(target=run_conversation, daemon=True)
            run_thread.start()
            
            # Wait for completion or timeout
            if not run_complete.wait(timeout=timeout_seconds):
                logger.error(f"OpenHands execution timed out after {timeout_seconds}s")
                # Note: We can't easily kill the thread, but we'll raise the error
                raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s. The operation may still be running in the background.")
            
            # Check if exception occurred
            if run_exception[0]:
                raise run_exception[0]
            
            # Capture after state
            after_files = self._capture_workspace_state(workspace_path)
            logger.info(f"   After state: {len(after_files)} files")
            if after_files:
                logger.info(f"   After files: {list(after_files.keys())[:5]}")
            else:
                logger.warning(f"   ⚠️  No files found in workspace after OpenHands execution!")
                logger.warning(f"   Workspace path: {workspace_path_abs}")
                logger.warning(f"   Workspace exists: {workspace_path_abs.exists()}")
                if workspace_path_abs.exists():
                    # List what's actually in the workspace
                    try:
                        actual_files = list(workspace_path_abs.rglob("*"))
                        logger.warning(f"   Actual files in workspace: {[str(f.relative_to(workspace_path_abs)) for f in actual_files if f.is_file()][:10]}")
                    except Exception as e:
                        logger.warning(f"   Could not list workspace files: {e}")
            
            # Generate diffs
            diffs = self._generate_diffs(before_files, after_files, "generation")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ OpenHands SDK completed in {duration:.2f}s")
            logger.info(f"   Files generated: {len(after_files)}")
            logger.info(f"   Diffs: {len(diffs)}")
            
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
        """Apply patch plan using OpenHands SDK"""
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands not available. Cannot apply patches without OpenHands.")
        
        workspace_path = Path(workspace_path)
        start_time = datetime.now()
        
        logger.info(f"🔧 Applying patch plan via OpenHands SDK")
        logger.info(f"   Workspace: {workspace_path}")
        
        # Build instructions for OpenHands
        instructions = self._build_instructions(patch_plan)
        
        # Write instructions to temp file
        instructions_file = self.artifacts_dir / f"openhands_instructions_{int(start_time.timestamp())}.txt"
        instructions_file.write_text(instructions)
        
        logger.info(f"   Instructions: {instructions_file}")
        
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
            model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
            if not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            llm = LLM(
                model=model,
                api_key=SecretStr(os.getenv("GOOGLE_AI_STUDIO_API_KEY")),
            )
            
            # Create agent with browser, file, and terminal tools
            # Disable auto-screenshots to prevent context overflow
            agent = Agent(
                llm=llm,
                tools=[
                    Tool(name=BrowserToolSet.name, params={"include_screenshot": False}),
                    Tool(name=FileEditorTool.name),
                    Tool(name=TerminalTool.name),
                ]
            )
            
            # Ensure workspace path is absolute and valid
            workspace_path_abs = workspace_path.resolve()
            logger.info(f"   OpenHands workspace: {workspace_path_abs}")
            
            # Create conversation with absolute workspace path
            conversation = Conversation(agent=agent, workspace=str(workspace_path_abs))
            
            # Send patch instructions and run
            logger.info("   Sending patch instructions to OpenHands agent...")
            logger.info(f"   Instructions length: {len(instructions)} characters")
            conversation.send_message(instructions)
            
            # Run with timeout (default 10 minutes, configurable via env var)
            timeout_seconds = float(os.getenv('OPENHANDS_TIMEOUT_SECONDS', '600'))  # 10 minutes default
            
            # Use threading to implement timeout for blocking call
            run_complete = threading.Event()
            run_exception = [None]
            
            def run_conversation():
                try:
                    conversation.run()
                    run_complete.set()
                except Exception as e:
                    run_exception[0] = e
                    run_complete.set()
            
            # Start conversation in separate thread
            run_thread = threading.Thread(target=run_conversation, daemon=True)
            run_thread.start()
            
            # Wait for completion or timeout
            if not run_complete.wait(timeout=timeout_seconds):
                logger.error(f"OpenHands patch execution timed out after {timeout_seconds}s")
                raise RuntimeError(f"OpenHands patch execution timed out after {timeout_seconds}s. The operation may still be running in the background.")
            
            # Check if exception occurred
            if run_exception[0]:
                raise run_exception[0]
            
            # Capture after state
            after_files = self._capture_workspace_state(workspace_path)
            
            # Determine which files were modified
            files_modified = list(set(after_files.keys()) | set(before_files.keys()))
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ OpenHands SDK patch completed in {duration:.2f}s")
            logger.info(f"   Files modified: {len(files_modified)}")
            
            return {
                "success": True,
                "files_modified": files_modified,
                "stdout": "OpenHands SDK patch execution completed",
                "stderr": "",
                "duration_seconds": duration,
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"   OpenHands SDK error: {e}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            
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
        """
        Capture current state of all files in workspace
        
        SECURITY: Only reads files within workspace_path (should be PROJECT_ROOT)
        """
        
        files_state = {}
        workspace_path = Path(workspace_path).resolve()
        
        if not workspace_path.exists():
            logger.warning(f"Workspace path does not exist: {workspace_path}")
            return files_state
        
        logger.info(f"Capturing workspace state from: {workspace_path}")
        
        for file_path in workspace_path.rglob("*"):
            # Security check: ensure file is within workspace
            try:
                file_resolved = file_path.resolve()
                if not file_resolved.is_relative_to(workspace_path):
                    logger.warning(f"Skipping file outside workspace: {file_path}")
                    continue
            except (ValueError, RuntimeError):
                logger.warning(f"Skipping invalid file path: {file_path}")
                continue
            
            # Skip hidden files and directories
            if file_path.is_file() and not file_path.name.startswith('.'):
                try:
                    relative_path = file_path.relative_to(workspace_path)
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    files_state[str(relative_path)] = content
                except Exception as e:
                    logger.debug(f"Could not read {file_path}: {e}")
                    pass  # Skip files that can't be read
        
        logger.info(f"Captured {len(files_state)} files")
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
    
    def _build_generation_prompt(self, task: str, requirements: Dict[str, Any] = None, template_file: str = None, workspace_path: str = None) -> str:
        """Build task prompt for OpenHands, optionally including template instructions"""
        
        prompt = f"{task}"
        
        # Check if index.html already exists in workspace (template was pre-loaded)
        index_exists = False
        if workspace_path:
            workspace_path_obj = Path(workspace_path) if isinstance(workspace_path, str) else workspace_path
            index_path = workspace_path_obj / "index.html"
            if index_path.exists():
                index_exists = True
                prompt += f"\n\n**CRITICAL: REPLACE THE ENTIRE MODULES ARRAY WITH GEOMETRY CONTENT**"
                prompt += f"\n- There is already an index.html file in your workspace (this is the template)"
                prompt += f"\n- You MUST edit this existing file - DO NOT create a new file from scratch"
                prompt += f"\n- Read the index.html file completely to understand its structure"
                prompt += f"\n\n**MANDATORY: REPLACE THE MODULES ARRAY**"
                prompt += f"\n- Find the line: `let modules = [`"
                prompt += f"\n- The current modules array has PLACEHOLDER content (Module 1: Introduction, Module 2: Advanced Concepts)"
                prompt += f"\n- You MUST REPLACE the ENTIRE modules array content with geometry content from the notes"
                prompt += f"\n- Delete ALL placeholder modules and create NEW modules based on the geometry notes"
                prompt += f"\n- Example: Create modules for 'Circles', 'Coordinate Geometry', etc. based on the notes provided"
                prompt += f"\n\n**EDITING STRATEGY:**"
                prompt += f"\n1. Read the file to see the exact format of the modules array"
                prompt += f"\n2. Use file_editor to replace the ENTIRE modules array content"
                prompt += f"\n3. The old_str should be: `let modules = [` followed by all the placeholder module objects until the closing `];`"
                prompt += f"\n4. The new_str should be: `let modules = [` followed by your NEW geometry modules, then `];`"
                prompt += f"\n5. If str_replace fails, try replacing just the content inside the array brackets"
                prompt += f"\n\n**MODULE STRUCTURE (from notes):**"
                prompt += f"\n- Create modules for: Circles (radius, diameter, circumference, area formulas)"
                prompt += f"\n- Create modules for: Coordinate Geometry (distance formula, midpoint, slope, parallel/perpendicular)"
                prompt += f"\n- Each module needs: title (e.g., 'Circles'), explanation (from notes), keyPoints (from notes), etc."
                prompt += f"\n- DO NOT use placeholder titles like 'Module 1: Introduction' - use actual geometry topic names"
                prompt += f"\n\n**CRITICAL: INTERACTIVE ELEMENTS (REQUIRED - NOT PLACEHOLDERS):**"
                prompt += f"\n- Each module MUST have an interactiveElement field with ACTUAL working HTML/JavaScript"
                prompt += f"\n- DO NOT leave placeholder text like 'Interactive content will be placed here'"
                prompt += f"\n- Create REAL interactive content:"
                prompt += f"\n  * For Circles: Create an interactive quiz with questions about radius/diameter/circumference/area"
                prompt += f"\n  * For Coordinate Geometry: Create an interactive exercise where users calculate distance/midpoint/slope"
                prompt += f"\n- The interactiveElement should be FULL HTML with working JavaScript (buttons, inputs, calculations, feedback)"
                prompt += f"\n- Example for Circles: Quiz with 3-5 questions, input fields for answers, 'Check Answer' buttons, correct/incorrect feedback"
                prompt += f"\n- Example for Coordinate Geometry: Interactive calculator where users enter coordinates and see distance/midpoint calculated"
                prompt += f"\n- The interactive content MUST be functional - users should be able to interact with it, not just see placeholder text"
                prompt += f"\n- Replace the placeholder `<div class=\"interactive-element\" id=\"interactive-element\">` content with your actual interactive HTML"
                prompt += f"\n\n**NAVIGATION BUTTONS:**"
                prompt += f"\n- prevButton disabled at first module, nextButton disabled at last module - this is CORRECT"
                prompt += f"\n- DO NOT modify this logic"
        
        # Legacy template_file parameter (for backwards compatibility)
        if template_file and Path(template_file).exists() and not index_exists:
            template_path = Path(template_file)
            # Get relative path from workspace if possible
            if workspace_path:
                workspace_path_obj = Path(workspace_path) if isinstance(workspace_path, str) else workspace_path
                try:
                    relative_template = template_path.relative_to(workspace_path_obj)
                    template_location = str(relative_template)
                except ValueError:
                    # Template is not relative to workspace, use filename
                    template_location = template_path.name
            else:
                template_location = template_path.name
            
            prompt += f"\n\n**CRITICAL: START WITH THE TEMPLATE FILE**"
            prompt += f"\n- The template file is located at: {template_location} (in your workspace)"
            prompt += f"\n- You MUST use this template as your starting point - DO NOT create from scratch"
            prompt += f"\n- First, read the {template_location} file to understand its structure"
            prompt += f"\n- Then, copy it to index.html and populate the `modules` array with content from the notes"
            prompt += f"\n- Create as many module objects as appropriate based on the content structure"
            prompt += f"\n- Preserve the template structure: navigation system, module loading functions, audio controls, notes panel, chatbot"
            prompt += f"\n- You can modify colors and remove specific cards, but the skeleton structure must remain"
            prompt += f"\n- Each module should have: title, videoId, explanation, keyPoints, timeline, funFact, interactiveElement, audioSources"
            prompt += f"\n\n**CRITICAL: YOUTUBE VIDEO EMBEDDING (REQUIRED):**"
            prompt += f"\n- YouTube videos have been found and saved to youtube_videos.json in your workspace"
            prompt += f"\n- READ the youtube_videos.json file to get the video IDs"
            prompt += f"\n- For each module, assign the MOST RELEVANT YouTube video ID to the videoId field"
            prompt += f"\n- DO NOT set videoId to null - you MUST use the actual YouTube video IDs from the JSON file"
            prompt += f"\n- Match videos to modules by topic (e.g., 'Circles' video for Circles module, 'Coordinate Geometry' video for Coordinate Geometry module)"
            prompt += f"\n- The template will automatically embed the video using the videoId - you just need to set the field"
            prompt += f"\n\n**CRITICAL: interactiveElement MUST contain ACTUAL working HTML/JavaScript, NOT placeholder text**"
            prompt += f"\n- Find and REPLACE the placeholder: 'Interactive content will be placed here (quizzes, exercises, interactive games, etc.)'"
            prompt += f"\n- Create REAL interactive content: working quiz questions with buttons/inputs/feedback, interactive calculators, drag-and-drop exercises"
            prompt += f"\n- For Circles module: Create a quiz with 3-5 questions about radius/diameter/circumference/area, with input fields and 'Check Answer' buttons"
            prompt += f"\n- For Coordinate Geometry module: Create an interactive calculator where users enter coordinates and see distance/midpoint/slope calculated"
            prompt += f"\n- The interactiveElement must be FULL HTML with working JavaScript - buttons that respond, inputs that calculate, feedback messages"
            prompt += f"\n- DO NOT leave placeholder text - create functional, interactive content that users can actually interact with"
            prompt += f"\n- The template already has all CSS and JavaScript inline - do NOT add external files"
            # Get TTS API key from environment (use GOOGLE_TTS_API_KEY if available, fallback to GOOGLE_AI_STUDIO_API_KEY)
            tts_api_key = os.getenv('GOOGLE_TTS_API_KEY') or os.getenv('GOOGLE_AI_STUDIO_API_KEY')
            if not tts_api_key:
                logger.warning("⚠️  TTS API key not set. Audio generation instructions will be skipped.")
                tts_api_key = "NOT_SET"
            
            prompt += f"\n\n**CRITICAL: TTS AUDIO GENERATION (MANDATORY - DO NOT SKIP):**"
            prompt += f"\n- You MUST generate audio files using Google Cloud Text-to-Speech API"
            if tts_api_key != "NOT_SET":
                prompt += f"\n- API Key: {tts_api_key} (use this key for TTS API calls)"
            else:
                prompt += f"\n- API Key: Use environment variable GOOGLE_TTS_API_KEY or GOOGLE_AI_STUDIO_API_KEY"
            prompt += f"\n- STEP 1: Install the library: pip install google-cloud-texttospeech"
            prompt += f"\n- STEP 2: Create a Python script (e.g., generate_audio.py) that:"
            prompt += f"\n  1. Imports: from google.cloud import texttospeech"
            prompt += f"\n  2. Creates a client: client = texttospeech.TextToSpeechClient()"
            prompt += f"\n  3. For EACH text section (explanation, each keyPoint, timeline events, funFact, interactive intro):"
            prompt += f"\n     - Creates synthesis_input with the text"
            prompt += f"\n     - Sets voice to 'en-US-Neural2-D' (or 'en-US-Standard-C' if unavailable)"
            prompt += f"\n     - Sets audio_config to MP3 encoding"
            prompt += f"\n     - Calls client.synthesize_speech()"
            prompt += f"\n     - Saves the audio_content to a file named: `audio-{{module-id}}-{{section}}-{{index}}.mp3`"
            prompt += f"\n- STEP 3: Run the script: python generate_audio.py"
            prompt += f"\n- STEP 4: After ALL audio files are generated, update the HTML file's modules array:"
            prompt += f"\n   - Populate the audioSources object in each module with the generated file paths"
            prompt += f"\n   - Example: audioSources: {{ 'explanation': 'audio-0-explanation.mp3', 'keypoint-0': 'audio-0-keypoint-0.mp3' }}"
            prompt += f"\n- STEP 5: If audio generation fails for any section, remove/hide the audio button for that section"
            prompt += f"\n- **DO NOT SKIP THIS STEP - Audio generation is REQUIRED, not optional**"
            prompt += f"\n- **You MUST use terminal access to run the Python script and generate the audio files**"
        
        # Add mobile/tablet requirement
        prompt += "\n\n**CRITICAL RESPONSIVE DESIGN REQUIREMENT**: The code must look good and function properly on mobile (375px) AND tablet (768px) devices. Use CSS media queries for responsive breakpoints, ensure touch targets are at least 44px on mobile, and prevent horizontal scrolling on all screen sizes."
        
        # Add specific requirements if provided
        if requirements:
            prompt += "\n\nAdditional requirements:\n"
            for category, reqs in requirements.items():
                if isinstance(reqs, list):
                    for req in reqs:
                        prompt += f"- {req}\n"
        
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
