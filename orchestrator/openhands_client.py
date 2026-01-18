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
import sys
import time
import httpx
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


class ManagedAPIServer:
    """
    Context manager for subprocess-managed OpenHands API server.
    
    Based on OpenHands examples/02_remote_agent_server pattern.
    Provides better isolation, observability, and future VSCode support.
    """
    
    def __init__(self, port: int = 8000, host: str = "127.0.0.1", artifacts_dir: Optional[Path] = None):
        self.port: int = port
        self.host: str = host
        self.process: Optional[subprocess.Popen] = None
        self.base_url: str = f"http://{host}:{port}"
        self.stdout_thread: Optional[threading.Thread] = None
        self.stderr_thread: Optional[threading.Thread] = None
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path.cwd() / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
    def _stream_output(self, stream, prefix, target_stream):
        """Stream output from subprocess to target stream with prefix."""
        try:
            log_file = self.artifacts_dir / f"openhands_server_{prefix.lower()}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                for line in iter(stream.readline, ""):
                    if line:
                        line_str = f"[{prefix}] {line}"
                        target_stream.write(line_str)
                        target_stream.flush()
                        f.write(line_str)
                        f.flush()
        except Exception as e:
            logger.error(f"Error streaming {prefix}: {e}")
        finally:
            stream.close()
    
    def __enter__(self):
        """Start the API server subprocess."""
        logger.info(f"Starting OpenHands API server on {self.base_url}...")
        
        # Start the server process
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "openhands.agent_server",
                "--port",
                str(self.port),
                "--host",
                self.host,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"LOG_JSON": "true", **os.environ},
        )
        
        # Start threads to stream stdout and stderr
        assert self.process is not None
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self.stdout_thread = threading.Thread(
            target=self._stream_output,
            args=(self.process.stdout, "SERVER", sys.stdout),
            daemon=True,
        )
        self.stderr_thread = threading.Thread(
            target=self._stream_output,
            args=(self.process.stderr, "SERVER", sys.stderr),
            daemon=True,
        )
        
        self.stdout_thread.start()
        self.stderr_thread.start()
        
        # Wait for server to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                response = httpx.get(f"{self.base_url}/health", timeout=1.0)
                if response.status_code == 200:
                    logger.info(f"✅ API server is ready at {self.base_url}")
                    return self
            except Exception:
                pass
            
            assert self.process is not None
            if self.process.poll() is not None:
                # Process has terminated
                raise RuntimeError(
                    "Server process terminated unexpectedly. "
                    "Check the server logs above for details."
                )
            
            time.sleep(1)
        
        raise RuntimeError(f"Server failed to start after {max_retries} seconds")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the API server subprocess."""
        if self.process:
            logger.info("Stopping OpenHands API server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing API server...")
                self.process.kill()
                self.process.wait()
            
            # Wait for streaming threads to finish
            time.sleep(0.5)
            logger.info("API server stopped.")


class LocalSubprocessOpenHandsClient(OpenHandsClient):
    """
    OpenHands client that uses the remote agent server pattern.
    
    Runs OpenHands agent server as subprocess for better isolation and observability.
    Can optionally enable VSCode access via DockerWorkspace in the future.
    """
    
    def __init__(self, artifacts_dir: Optional[Path] = None, use_remote_server: bool = None):
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else Path.cwd() / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        # Default to False (direct SDK) if not specified - remote server seems to be crashing
        # Can be enabled via OPENHANDS_USE_REMOTE_SERVER env var
        if use_remote_server is None:
            env_value = os.getenv("OPENHANDS_USE_REMOTE_SERVER", "false")
            use_remote_server = env_value.lower() in ("true", "1", "yes")
            logger.info(f"   OpenHands client: use_remote_server from env: {env_value} -> {use_remote_server}")
        else:
            logger.info(f"   OpenHands client: use_remote_server explicitly set to: {use_remote_server}")
        self.use_remote_server = use_remote_server
        logger.info(f"   ✅ Final setting: use_remote_server={self.use_remote_server}")
        
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
    
    def execute_todo_task(self, todo: Dict[str, Any], workspace_path: str, all_modules_info: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a single todo task. This is called for each module one at a time.
        
        Args:
            todo: Todo item with type, title, description, module_data, etc.
            workspace_path: Path to workspace
            all_modules_info: List of all module information from planner (for context)
        
        Returns:
            Dict with success, files_generated, etc.
        """
        start_time = datetime.now()
        workspace_path = Path(workspace_path)
        
        if not self.openhands_available:
            raise RuntimeError("OpenHands not available. Cannot generate code without OpenHands.")
        
        # Build task-specific prompt
        task_prompt = self._build_todo_prompt(todo, all_modules_info, workspace_path)
        
        # Save prompt for debugging
        prompt_file = self.artifacts_dir / f"todo_{todo['id']}_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        prompt_file.write_text(task_prompt)
        logger.info(f"   Todo prompt saved: {prompt_file}")
        
        # Run OpenHands via Python SDK
        try:
            from openhands.sdk import LLM, Agent, Conversation, Workspace, Tool
            from openhands.tools.file_editor import FileEditorTool
            from openhands.tools.terminal import TerminalTool
            from openhands.tools.preset.default import get_default_agent
            from pydantic import SecretStr
            
            # Capture before state
            before_files = self._capture_workspace_state(workspace_path)
            
            # Configure LLM
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            if not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            llm = LLM(
                model=model,
                api_key=SecretStr(os.getenv("GOOGLE_AI_STUDIO_API_KEY")),
            )
            
            # Use OpenHands' default agent which includes planning capabilities
            # According to OpenHands docs, get_default_agent() should include FileEditorTool by default
            # The agent automatically sees built-in tools when properly configured
            
            try:
                # Try using get_default_agent - it should include FileEditorTool automatically
                agent = get_default_agent(
                    llm=llm,
                    cli_mode=True,  # Disable browser tools for code generation
                )
                # Log available tools for debugging
                if hasattr(agent, 'tools'):
                    tool_names = [getattr(t, 'name', str(t)) for t in agent.tools] if agent.tools else []
                    logger.info(f"   ✅ Default agent created with {len(tool_names)} tools")
                    logger.info(f"   Available tools: {', '.join(tool_names[:5])}{'...' if len(tool_names) > 5 else ''}")
                else:
                    logger.info("   ✅ Default agent created (tools not inspectable)")
            except Exception as agent_error:
                logger.warning(f"⚠️  Failed to create default agent: {agent_error}")
                logger.info("   Creating agent with explicit Tool references (using Tool.name pattern)...")
                # Fallback: create agent with explicit tool references using Tool(name=...) pattern
                # This matches the OpenHands documentation pattern
                agent = Agent(
                    llm=llm,
                    tools=[
                        Tool(name=FileEditorTool.name),
                        Tool(name=TerminalTool.name),
                    ],
                )
                logger.info("   ✅ Fallback agent created with explicit Tool(name=...) references")
            
            # Use remote agent server pattern if enabled (better observability, future VSCode support)
            if self.use_remote_server:
                # Use ManagedAPIServer for remote workspace
                server_port = int(os.getenv("OPENHANDS_SERVER_PORT", "8000"))
                with ManagedAPIServer(port=server_port, artifacts_dir=self.artifacts_dir) as server:
                    # Create remote workspace
                    workspace = Workspace(host=server.base_url, path=str(workspace_path.resolve()))
                    
                    # Create conversation (automatically becomes RemoteConversation)
                    conversation = Conversation(agent=agent, workspace=workspace)
                    
                    logger.info(f"   Using remote agent server at {server.base_url}")
                    logger.info(f"   Before state: {len(before_files)} files")
                    
                    # Send task prompt
                    conversation.send_message(task_prompt)
                    
                    # Run with timeout
                    timeout_seconds = float(os.getenv('OPENHANDS_TIMEOUT_SECONDS', '600'))
                    run_complete = threading.Event()
                    run_exception = [None]
                    
                    def run_conversation():
                        try:
                            conversation.run()
                            run_complete.set()
                        except Exception as e:
                            run_exception[0] = e
                            run_complete.set()
                    
                    run_thread = threading.Thread(target=run_conversation, daemon=True)
                    run_thread.start()
                    
                    if not run_complete.wait(timeout=timeout_seconds):
                        logger.error(f"OpenHands execution timed out after {timeout_seconds}s")
                        raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s")
                    
                    if run_exception[0]:
                        raise run_exception[0]
            else:
                # Direct SDK usage (original pattern)
                workspace = Workspace(path=str(workspace_path.resolve()))
                conversation = Conversation(agent=agent, workspace=workspace)
                
                logger.info(f"   Using direct SDK (local workspace)")
                logger.info(f"   Before state: {len(before_files)} files")
                
                # Send task prompt
                conversation.send_message(task_prompt)
                
                # Run with timeout
                timeout_seconds = float(os.getenv('OPENHANDS_TIMEOUT_SECONDS', '600'))
                run_complete = threading.Event()
                run_exception = [None]
                
                def run_conversation():
                    try:
                        conversation.run()
                        run_complete.set()
                    except Exception as e:
                        run_exception[0] = e
                        run_complete.set()
                
                run_thread = threading.Thread(target=run_conversation, daemon=True)
                run_thread.start()
                
                if not run_complete.wait(timeout=timeout_seconds):
                    logger.error(f"OpenHands execution timed out after {timeout_seconds}s")
                    raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s")
                
                if run_exception[0]:
                    raise run_exception[0]
            
            # Capture after state
            after_files = self._capture_workspace_state(workspace_path)
            logger.info(f"   After state: {len(after_files)} files")
            
            # Determine what changed
            files_generated = []
            for filepath in after_files:
                if filepath not in before_files or after_files[filepath] != before_files[filepath]:
                    files_generated.append(filepath)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Todo '{todo['title']}' completed in {duration:.2f}s")
            logger.info(f"   Files modified: {len(files_generated)}")
            
            return {
                "success": True,
                "files_generated": files_generated,
                "duration_seconds": duration,
                "todo_id": todo['id'],
                "todo_title": todo['title']
            }
            
        except Exception as e:
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            
            # Check if this is a FileEditorTool validation error
            if "FileEditorTool" in error_msg and ("validation error" in error_msg.lower() or "Field required" in error_msg):
                logger.error(f"❌ Todo execution failed: FileEditorTool validation error")
                logger.error(f"   This usually means the agent called file_editor with missing or empty parameters")
                logger.error(f"   Error details: {error_msg}")
                logger.error(f"   Full traceback:\n{error_traceback}")
                logger.error(f"   💡 Suggestion: The agent may need clearer instructions on how to use file_editor tool")
            else:
                logger.error(f"❌ Todo execution failed: {error_msg}")
                logger.error(f"   Full traceback:\n{error_traceback}")
            
            return {
                "success": False,
                "error": error_msg,
                "error_type": "FileEditorTool_validation" if "FileEditorTool" in error_msg and "Field required" in error_msg else "unknown",
                "todo_id": todo['id'],
                "todo_title": todo['title']
            }
    
    def _build_todo_prompt(self, todo: Dict[str, Any], all_modules_info: List[Dict[str, Any]], workspace_path: Path) -> str:
        """Build a focused prompt for a single todo task"""
        
        todo_type = todo.get('type')
        workspace_path_obj = Path(workspace_path) if isinstance(workspace_path, str) else workspace_path
        
        # Check if index.html exists
        index_exists = (workspace_path_obj / "index.html").exists()
        
        prompt = f"**TASK: {todo['title']}**\n\n"
        prompt += f"{todo['description']}\n\n"
        
        if todo_type == 'setup':
            prompt += self._build_setup_prompt(workspace_path_obj, index_exists)
        elif todo_type == 'module':
            prompt += self._build_module_prompt(todo, all_modules_info, workspace_path_obj, index_exists)
        elif todo_type == 'validation':
            prompt += self._build_validation_prompt(workspace_path_obj, index_exists)
        
        return prompt
    
    def _build_setup_prompt(self, workspace_path: Path, index_exists: bool) -> str:
        """Build prompt for setup todo"""
        prompt = "**SETUP TASK - READ ONLY, NO MODIFICATIONS:**\n\n"
        prompt += "**THIS IS A READ-ONLY TASK - DO NOT CREATE OR MODIFY ANYTHING**\n"
        prompt += "- Use file_editor tool with action_type='read' to read index.html\n"
        prompt += "- DO NOT use action_type='edit' or 'create' in this task\n"
        prompt += "- DO NOT initialize anything, set up anything, or create any structure\n"
        prompt += "- This task is ONLY for reading and understanding the existing structure\n\n"
        prompt += "**STEPS (READ ONLY):**\n"
        prompt += "1. Read the existing index.html file completely using file_editor with action_type='read'\n"
        prompt += "2. Identify the `modules` array in the JavaScript section\n"
        prompt += "3. Understand the template structure: navigation, audio controls, notes panel, chatbot\n"
        prompt += "4. DO NOT modify anything - just read and understand the structure\n"
        if not index_exists:
            prompt += "\n⚠️  WARNING: index.html does not exist. This is unexpected. Report this issue.\n"
        return prompt
    
    def _build_module_prompt(self, todo: Dict[str, Any], all_modules_info: List[Dict[str, Any]], workspace_path: Path, index_exists: bool) -> str:
        """Build prompt for a single module todo"""
        module_data = todo.get('module_data', {})
        module_index = todo.get('module_index')
        requirements = todo.get('requirements', {})
        interactive_experiences = todo.get('interactive_experiences', [])
        
        prompt = f"**MODULE {module_index + 1} CREATION TASK - CREATE COMPLETE MODULE IN ONE OPERATION:**\n\n"
        
        prompt += "**CRITICAL: THIS IS A SINGLE, ATOMIC TASK - DO NOT BREAK IT DOWN INTO STEPS**\n"
        prompt += "- You MUST create the COMPLETE module object with ALL fields in ONE file edit operation\n"
        prompt += "- DO NOT create separate tasks for 'initializing', 'setting up', 'adding fields', etc.\n"
        prompt += "- DO NOT break this into multiple file_editor calls\n"
        prompt += "- Create the ENTIRE module object with ALL required fields in a SINGLE edit operation\n\n"
        
        if not index_exists:
            prompt += "⚠️  ERROR: index.html does not exist. Setup task should have been completed first.\n\n"
        
        prompt += "**CRITICAL FILE OPERATION RULES:**\n"
        prompt += "- The file path is: index.html (relative to workspace)\n"
        prompt += "- ALWAYS check if index.html exists before modifying it\n"
        prompt += "- If index.html exists, you MUST use `edit` or `write` command, NEVER use `create`\n"
        prompt += "- The `create` command will FAIL with error: \"File already exists. Cannot overwrite files using command create\"\n"
        prompt += "- Use file_editor tool with action_type='edit' and provide a clear description\n\n"
        
        prompt += f"**YOUR SINGLE TASK:** Add the COMPLETE Module {module_index + 1} object to the `modules` array in index.html\n\n"
        
        # Build complete module object structure
        module_title = module_data.get('title', 'TBD from notes')
        prompt += "**COMPLETE MODULE OBJECT STRUCTURE (CREATE ALL OF THIS IN ONE OPERATION):**\n\n"
        prompt += "```javascript\n"
        prompt += f"{{\n"
        prompt += f"  title: \"{module_title}\",\n"
        
        if requirements.get('videoId'):
            prompt += f"  videoId: \"{requirements['videoId']}\",\n"
        else:
            prompt += f"  videoId: null,  // Extract from YouTube links if provided\n"
        
        if requirements.get('explanation'):
            explanation = requirements['explanation'].replace('"', '\\"')
            prompt += f"  explanation: \"{explanation}\",\n"
        else:
            prompt += f"  explanation: \"\",  // Add explanation text from notes\n"
        
        if requirements.get('keyPoints'):
            key_points = requirements['keyPoints']
            if isinstance(key_points, list):
                # Escape quotes properly for JavaScript string
                escaped_points = []
                for kp in key_points:
                    # Replace double quotes with escaped quotes
                    escaped_kp = str(kp).replace('"', '\\"')
                    escaped_points.append(f'"{escaped_kp}"')
                points_str = ', '.join(escaped_points)
                prompt += f"  keyPoints: [{points_str}],\n"
            else:
                prompt += f"  keyPoints: [],  // Add key points array from notes\n"
        else:
            prompt += f"  keyPoints: [],  // Add key points array from notes\n"
        
        if requirements.get('timeline'):
            prompt += f"  timeline: {json.dumps(requirements['timeline'])},  // Timeline events if applicable\n"
        else:
            prompt += f"  timeline: [],  // Timeline events if applicable\n"
        
        if requirements.get('funFact'):
            fun_fact = requirements['funFact'].replace('"', '\\"')
            prompt += f"  funFact: \"{fun_fact}\",\n"
        else:
            prompt += f"  funFact: \"\",  // Add fun fact from notes\n"
        
        prompt += f"  interactiveElement: `...`,  // FULL HTML with JavaScript (see below)\n"
        prompt += f"  audioSources: {{}}  // Will be populated if audio generation succeeds\n"
        prompt += f"}}\n"
        prompt += "```\n\n"
        
        prompt += "**CRITICAL: interactiveElement (REQUIRED - FUN ACTIVITY, NOT QUIZ):**\n"
        prompt += "- **NEVER CREATE QUIZZES, TESTS, OR MULTIPLE-CHOICE QUESTIONS**\n"
        prompt += "- **MUST CREATE FUN INTERACTIVE ACTIVITY**: calculator, simulation, game, manipulative\n"
        
        if interactive_experiences:
            for exp in interactive_experiences:
                exp_name = exp.get('name', 'Interactive Activity')
                exp_type = exp.get('type', 'calculator')
                prompt += f"- Create: {exp_name} (type: {exp_type})\n"
                if exp.get('what_user_does'):
                    prompt += f"  * User actions: {', '.join(exp['what_user_does'])}\n"
                if exp.get('what_user_sees'):
                    prompt += f"  * User sees: {', '.join(exp['what_user_sees'])}\n"
        
        prompt += "- The interactiveElement must be a FULL HTML string with embedded JavaScript\n"
        prompt += "- Include: inputs, buttons, calculations, visual feedback\n"
        prompt += "- Make it FUN and engaging, NOT test-like\n"
        prompt += "- Example: Calculator with inputs → shows calculated results\n"
        prompt += "- Example: Interactive tool with user inputs → displays computed outputs\n\n"
        
        prompt += "**HOW TO EXECUTE THIS TASK (ONE OPERATION ONLY):**\n"
        prompt += "1. Read the current index.html file to find the `modules` array\n"
        prompt += f"2. Use file_editor tool ONCE with:\n"
        prompt += f"   - action_type: 'edit'\n"
        prompt += f"   - description: 'Add complete Module {module_index + 1} ({module_title}) to modules array'\n"
        prompt += f"   - file_path: 'index.html'\n"
        prompt += f"   - Edit the modules array to add the COMPLETE module object (all fields) at the correct position\n"
        prompt += f"3. The module object MUST include ALL fields: title, videoId, explanation, keyPoints, timeline, funFact, interactiveElement, audioSources\n"
        prompt += f"4. DO NOT make multiple edits - create the complete module in ONE edit operation\n\n"
        
        prompt += "**VERIFICATION:**\n"
        prompt += "- After the single edit, verify the complete module appears in the modules array\n"
        prompt += "- Verify interactiveElement contains actual HTML/JS, not placeholder text\n"
        prompt += "- Verify all required fields are present in the module object\n"
        
        return prompt
    
    def _build_validation_prompt(self, workspace_path: Path, index_exists: bool) -> str:
        """Build prompt for validation todo"""
        prompt = "**FINAL VALIDATION TASK:**\n\n"
        prompt += "**CRITICAL: DO NOT DELETE ANY FILES, ESPECIALLY SCREENSHOTS OR ARTIFACTS**\n"
        prompt += "- Only modify index.html if needed to fix issues\n"
        prompt += "- Do NOT delete any files in the workspace\n"
        prompt += "- Do NOT delete screenshots, videos, or any artifacts\n"
        prompt += "- Do NOT run cleanup commands that remove files\n\n"
        prompt += "**VALIDATION STEPS:**\n"
        prompt += "1. Verify all modules are present in the modules array\n"
        prompt += "2. Check that NO placeholder text remains (especially in interactiveElement)\n"
        prompt += "3. Verify all interactive elements are FUN activities (calculators/simulations), NOT quizzes\n"
        prompt += "4. Verify JavaScript code uses `module.interactiveElement` not `module.quiz`\n"
        prompt += "5. Test that navigation works between all modules\n"
        prompt += "6. Ensure no console errors\n"
        prompt += "7. Fix any issues found in index.html ONLY\n"
        prompt += "8. DO NOT delete any files - only edit index.html to fix problems\n"
        return prompt
    
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
            from openhands.sdk import LLM, Agent, Conversation, Workspace, Tool
            from openhands.tools.browser_use import BrowserToolSet
            from openhands.tools.file_editor import FileEditorTool
            from openhands.tools.terminal import TerminalTool
            from openhands.tools.preset.default import get_default_agent
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
            
            # Use OpenHands' default agent which includes planning capabilities
            # According to OpenHands docs, get_default_agent() should include FileEditorTool by default
            try:
                agent = get_default_agent(
                    llm=llm,
                    cli_mode=True,  # Disable browser tools for code generation
                )
                if hasattr(agent, 'tools'):
                    tool_names = [getattr(t, 'name', str(t)) for t in agent.tools] if agent.tools else []
                    logger.info(f"   ✅ Default agent created with {len(tool_names)} tools")
            except Exception as agent_error:
                logger.warning(f"⚠️  Failed to create default agent: {agent_error}")
                logger.info("   Creating agent with explicit Tool references...")
                agent = Agent(
                    llm=llm,
                    tools=[
                        Tool(name=FileEditorTool.name),
                        Tool(name=TerminalTool.name),
                    ],
                )
                logger.info("   ✅ Fallback agent created with explicit Tool(name=...) references")
            
            # Ensure workspace path is absolute and valid
            workspace_path_abs = workspace_path.resolve()
            logger.info(f"   OpenHands workspace: {workspace_path_abs}")
            logger.info(f"   Using OpenHands default agent with built-in planning tools")
            logger.info(f"   🔧 Remote server setting: use_remote_server={self.use_remote_server}")
            
            # Use remote agent server pattern if enabled (better observability, future VSCode support)
            # DISABLED BY DEFAULT - remote server is crashing, use direct SDK instead
            if self.use_remote_server:
                logger.warning("   ⚠️  Remote server enabled - attempting to start...")
                try:
                    # Use ManagedAPIServer for remote workspace
                    server_port = int(os.getenv("OPENHANDS_SERVER_PORT", "8000"))
                    with ManagedAPIServer(port=server_port, artifacts_dir=self.artifacts_dir) as server:
                        # Create remote workspace
                        workspace = Workspace(host=server.base_url, path=str(workspace_path_abs))
                        
                        # Create conversation (automatically becomes RemoteConversation)
                        conversation = Conversation(agent=agent, workspace=workspace)
                        
                        logger.info(f"   Using remote agent server at {server.base_url}")
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
                            raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s. The operation may still be running in the background.")
                        
                        # Check if exception occurred
                        if run_exception[0]:
                            raise run_exception[0]
                except RuntimeError as e:
                    if "Server process terminated" in str(e) or "Server failed to start" in str(e):
                        logger.error(f"   ❌ Remote server failed: {e}")
                        logger.warning("   🔄 Falling back to direct SDK mode...")
                        # Fall through to direct SDK mode below
                        self.use_remote_server = False
                    else:
                        raise
            
            # Direct SDK usage (fallback if remote server fails or disabled)
            if not self.use_remote_server:
                # Direct SDK usage (original pattern)
                workspace = Workspace(path=str(workspace_path_abs))
                conversation = Conversation(agent=agent, workspace=workspace)
                
                logger.info(f"   Using direct SDK (local workspace)")
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
            from openhands.sdk import LLM, Agent, Conversation, Workspace
            from openhands.tools import Tool
            from openhands.tools.browser_use import BrowserToolSet
            from openhands.tools.file_editor import FileEditorTool
            from openhands.tools.terminal import TerminalTool
            from openhands.tools.preset.default import get_default_agent
            from pydantic import SecretStr
            
            # Capture before state
            before_files = self._capture_workspace_state(workspace_path)
            
            # Configure LLM (using Gemini AI Studio, not Vertex AI)
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            if not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            llm = LLM(
                model=model,
                api_key=SecretStr(os.getenv("GOOGLE_AI_STUDIO_API_KEY")),
            )
            
            # Use OpenHands' default agent which includes planning capabilities
            # According to OpenHands docs, get_default_agent() should include FileEditorTool by default
            try:
                agent = get_default_agent(
                    llm=llm,
                    cli_mode=True,  # Disable browser tools for code generation
                )
                if hasattr(agent, 'tools'):
                    tool_names = [getattr(t, 'name', str(t)) for t in agent.tools] if agent.tools else []
                    logger.info(f"   ✅ Default agent created with {len(tool_names)} tools")
            except Exception as agent_error:
                logger.warning(f"⚠️  Failed to create default agent: {agent_error}")
                logger.info("   Creating agent with explicit Tool references...")
                agent = Agent(
                    llm=llm,
                    tools=[
                        Tool(name=FileEditorTool.name),
                        Tool(name=TerminalTool.name),
                    ],
                )
                logger.info("   ✅ Fallback agent created with explicit Tool(name=...) references")
            
            # Ensure workspace path is absolute and valid
            workspace_path_abs = workspace_path.resolve()
            logger.info(f"   OpenHands workspace: {workspace_path_abs}")
            
            # Use remote agent server pattern if enabled (better observability, future VSCode support)
            if self.use_remote_server:
                # Use ManagedAPIServer for remote workspace
                server_port = int(os.getenv("OPENHANDS_SERVER_PORT", "8000"))
                with ManagedAPIServer(port=server_port, artifacts_dir=self.artifacts_dir) as server:
                    # Create remote workspace
                    workspace = Workspace(host=server.base_url, path=str(workspace_path_abs))
                    
                    # Create conversation (automatically becomes RemoteConversation)
                    conversation = Conversation(agent=agent, workspace=workspace)
                    
                    logger.info(f"   Using remote agent server at {server.base_url}")
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
                        logger.error(f"OpenHands execution timed out after {timeout_seconds}s")
                        raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s. The operation may still be running in the background.")
                    
                    # Check if exception occurred
                    if run_exception[0]:
                        raise run_exception[0]
            else:
                # Direct SDK usage (original pattern)
                workspace = Workspace(path=str(workspace_path_abs))
                conversation = Conversation(agent=agent, workspace=workspace)
                
                logger.info(f"   Using direct SDK (local workspace)")
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
                    logger.error(f"OpenHands execution timed out after {timeout_seconds}s")
                    raise RuntimeError(f"OpenHands execution timed out after {timeout_seconds}s. The operation may still be running in the background.")
                
                # Check if exception occurred
                if run_exception[0]:
                    raise run_exception[0]
            
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
        """
        Build task prompt for OpenHands, optionally including template instructions.
        
        Note: The `task` parameter contains the planner's openhands_build_prompt instructions,
        which are detailed instructions generated by the planner based on notes.
        We add template-specific instructions on top of these planner instructions.
        """
        
        # The task parameter already contains the planner's detailed instructions
        # (openhands_build_prompt from the planner output)
        prompt = f"{task}"
        
        # Check if index.html already exists in workspace (template was pre-loaded)
        index_exists = False
        if workspace_path:
            workspace_path_obj = Path(workspace_path) if isinstance(workspace_path, str) else workspace_path
            index_path = workspace_path_obj / "index.html"
            if index_path.exists():
                index_exists = True
                prompt += f"\n\n**CRITICAL: FOLLOW THE INSTRUCTIONS PROVIDED ABOVE**"
                prompt += f"\n- There is already an index.html file in your workspace (this is the template)"
                prompt += f"\n- **FILE OPERATION RULES:**"
                prompt += f"\n  * The file path is: index.html (relative to workspace)"
                prompt += f"\n  * ALWAYS check if a file exists before modifying it"
                prompt += f"\n  * If index.html already exists (which it does), you MUST use `edit` or `write` command, NEVER use `create`"
                prompt += f"\n  * The `create` command will FAIL with error: \"File already exists. Cannot overwrite files using command create\""
                prompt += f"\n  * To edit an existing file, use: `file_editor` tool with `edit` operation, or use `write` tool"
                prompt += f"\n- You MUST edit this existing file - DO NOT create a new file from scratch"
                prompt += f"\n- Read the index.html file completely to understand its structure"
                prompt += f"\n\n**MANDATORY: REPLACE THE MODULES ARRAY**"
                prompt += f"\n- Find the line: `let modules = [`"
                prompt += f"\n- The current modules array has PLACEHOLDER content (Module 1: Introduction, Module 2: Advanced Concepts)"
                prompt += f"\n- You MUST REPLACE the ENTIRE modules array content following the instructions provided above"
                prompt += f"\n- Delete ALL placeholder modules and create NEW modules as specified in the instructions above"
                prompt += f"\n- Follow the module specifications and content described in the instructions above"
                prompt += f"\n\n**EDITING STRATEGY:**"
                prompt += f"\n1. Read the file to see the exact format of the modules array"
                prompt += f"\n2. Use file_editor with `edit` operation (NOT `create`) to replace the ENTIRE modules array content"
                prompt += f"\n3. Remember: index.html already exists, so use `edit` or `write` command, never `create`"
                prompt += f"\n4. The old_str should be: `let modules = [` followed by all the placeholder module objects until the closing `];`"
                prompt += f"\n5. The new_str should be: `let modules = [` followed by your NEW modules, then `];`"
                prompt += f"\n6. If str_replace fails, try replacing just the content inside the array brackets"
                prompt += f"\n\n**MODULE STRUCTURE (from instructions above):**"
                prompt += f"\n- Create modules based on the topics and structure specified in the instructions above"
                prompt += f"\n- Each module needs: title, explanation, keyPoints, etc. as specified in the instructions above"
                prompt += f"\n- DO NOT use placeholder titles like 'Module 1: Introduction' - use actual topic names as specified in the instructions above"
                prompt += f"\n\n**CRITICAL: INTERACTIVE ELEMENTS (REQUIRED - FUN ACTIVITIES, NOT QUIZZES):**"
                prompt += f"\n- **NEVER CREATE QUIZZES, TESTS, OR MULTIPLE-CHOICE QUESTIONS**"
                prompt += f"\n- **INTERACTIVE ACTIVITIES MUST BE FUN, ENGAGING, AND GAME-LIKE**"
                prompt += f"\n- **IGNORE THE EXISTING `quiz` FIELD IN THE TEMPLATE - DO NOT USE IT**"
                prompt += f"\n- **YOU MUST USE `interactiveElement` FIELD INSTEAD OF `quiz`**"
                prompt += f"\n- Each module MUST have an `interactiveElement` field (NOT `quiz`) with ACTUAL working HTML/JavaScript code as a STRING"
                prompt += f"\n- The `interactiveElement` field must contain a complete HTML string with embedded JavaScript"
                prompt += f"\n- DO NOT use the `quiz` object structure - that is OLD/PLACEHOLDER code"
                prompt += f"\n- DO NOT create multiple-choice questions, true/false questions, or any test-like content"
                prompt += f"\n- DO NOT leave placeholder text like 'Interactive content will be placed here'"
                prompt += f"\n- **YOU MUST ALSO UPDATE THE JAVASCRIPT CODE** that renders interactive elements:"
                prompt += f"\n  * Find the code that checks `if (module.quiz)` (around line 1536)"
                prompt += f"\n  * REPLACE it with code that checks `if (module.interactiveElement)`"
                prompt += f"\n  * Set `interactiveElement.innerHTML = module.interactiveElement` (the HTML string from the field)"
                prompt += f"\n- **CREATE FUN INTERACTIVE ACTIVITIES** based on the planner's instructions:"
                prompt += f"\n  * Interactive CALCULATORS: Users input values and see instant calculations"
                prompt += f"\n  * Interactive SIMULATIONS: Visual, hands-on experiences where users manipulate values and see results"
                prompt += f"\n  * Interactive GAMES: Engaging, playful activities that teach concepts through interaction"
                prompt += f"\n  * Interactive MANIPULATIVES: Drag-and-drop, sliders, visual tools that let users explore concepts"
                prompt += f"\n  * Follow the EXACT interactiveElement specifications from the planner prompt above"
                prompt += f"\n  * Create interactive tools relevant to the subject matter in the notes"
                prompt += f"\n- The interactiveElement should be FULL HTML with working JavaScript (buttons, inputs, calculations, visual feedback)"
                prompt += f"\n- The interactive content MUST be functional and FUN - users should enjoy interacting with it, not feel like they're taking a test"
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
            
            prompt += f"\n\n**CRITICAL: EDIT THE EXISTING TEMPLATE FILE**"
            prompt += f"\n- The template file is already in your workspace as index.html"
            prompt += f"\n- You MUST edit the existing index.html file - DO NOT create from scratch"
            prompt += f"\n- First, read the index.html file to understand its structure"
            prompt += f"\n- Then, edit it directly and populate the `modules` array following the instructions provided above"
            prompt += f"\n- Create as many module objects as appropriate based on the content structure"
            prompt += f"\n- Preserve the template structure: navigation system, module loading functions, audio controls, notes panel, chatbot"
            prompt += f"\n- You can modify colors and remove specific cards, but the skeleton structure must remain"
            prompt += f"\n- Each module should have: title, videoId, explanation, keyPoints, timeline, funFact, interactiveElement, audioSources"
            prompt += f"\n\n**CRITICAL: YOUTUBE VIDEO EMBEDDING (REQUIRED):**"
            prompt += f"\n- YouTube videos have been found and saved to youtube_videos.json in your workspace"
            prompt += f"\n- READ the youtube_videos.json file to get the video IDs"
            prompt += f"\n- For each module, assign the MOST RELEVANT YouTube video ID to the videoId field"
            prompt += f"\n- DO NOT set videoId to null - you MUST use the actual YouTube video IDs from the JSON file"
            prompt += f"\n- Match videos to modules by topic - assign the most relevant video to each module based on content"
            prompt += f"\n- The template will automatically embed the video using the videoId - you just need to set the field"
            prompt += f"\n\n**CRITICAL: interactiveElement MUST contain ACTUAL working HTML/JavaScript, NOT placeholder text**"
            prompt += f"\n- **NEVER CREATE QUIZZES, TESTS, OR MULTIPLE-CHOICE QUESTIONS - ONLY FUN INTERACTIVE ACTIVITIES**"
            prompt += f"\n- **DO NOT USE `quiz` FIELD - USE `interactiveElement` FIELD INSTEAD**"
            prompt += f"\n- Find and REPLACE the placeholder: 'Interactive content will be placed here (quizzes, exercises, interactive games, etc.)'"
            prompt += f"\n- **UPDATE THE JAVASCRIPT**: Replace `if (module.quiz)` with `if (module.interactiveElement)` and set `innerHTML = module.interactiveElement`"
            prompt += f"\n- Create FUN interactive content: interactive calculators, visual simulations, engaging games, drag-and-drop manipulatives"
            prompt += f"\n- **FORBIDDEN**: Multiple-choice questions, true/false questions, fill-in-the-blank tests, any quiz-like content"
            prompt += f"\n- **REQUIRED**: Interactive calculators, visual tools, simulations, games that let users explore and discover concepts"
            prompt += f"\n- Follow the EXACT interactiveElement specifications from the planner prompt"
            prompt += f"\n- Create interactive tools that are relevant to the subject matter - FUN and interactive, NOT a quiz"
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
