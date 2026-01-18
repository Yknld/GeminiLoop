"""
Agentic Evaluator - Gemini Controls Browser Directly

Instead of scripted tests, Gemini autonomously explores the page using MCP browser tools.
Implements an observe→act loop where Gemini sees screenshots and chooses actions.

IMPROVEMENTS:
- Multimodal exploration (sends PIL.Image screenshots to Gemini)
- Robust function calling parsing
- Expanded toolset (wait_for, hover, press_key, get_url, dom_snapshot)
- Structured verification (before/after signals)
- Better interactive element discovery with stable selectors
- Dialog detection and handling
- Comprehensive artifacts and logging
"""

import os
import logging
import json
import asyncio
import hashlib
from dataclasses import asdict
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
import PIL.Image

from .evaluator import (
    GeminiEvaluator, 
    EvaluationResult,
    EvaluationIssue,
    BrowserObservation,
    EVALUATION_RUBRIC
)

logger = logging.getLogger(__name__)


# MCP Browser Tools as Gemini Function Declarations
# Using dict format with UPPERCASE type enums (required by google.generativeai)
BROWSER_TOOLS = [
    {
        "name": "browser_click",
        "description": "Click an element on the page using a CSS selector",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {
                    "type": "STRING",
                    "description": "CSS selector for the element to click (e.g., 'button', '#submit', '.card')"
                }
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into an input field",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {
                    "type": "STRING",
                    "description": "CSS selector for the input field"
                },
                "text": {
                    "type": "STRING",
                    "description": "Text to type into the field"
                }
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the page up or down",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "direction": {
                    "type": "STRING",
                    "description": "Direction to scroll: 'up' or 'down'"
                },
                "amount": {
                    "type": "INTEGER",
                    "description": "Amount to scroll in pixels (default: 500)"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "browser_evaluate",
        "description": "Execute JavaScript in the browser and return the result",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {
                    "type": "STRING",
                    "description": "JavaScript expression to evaluate"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "browser_wait_for",
        "description": "Wait for a condition (selector appears, text appears, or timeout)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {
                    "type": "STRING",
                    "description": "CSS selector to wait for (optional)"
                },
                "text": {
                    "type": "STRING",
                    "description": "Text to wait for on page (optional)"
                },
                "timeout": {
                    "type": "INTEGER",
                    "description": "Timeout in milliseconds (default: 3000)"
                }
            },
            "required": []
        }
    },
    {
        "name": "browser_hover",
        "description": "Hover over an element to reveal tooltips or trigger hover effects",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {
                    "type": "STRING",
                    "description": "CSS selector for the element to hover over"
                }
            },
            "required": ["selector"]
        }
    },
    {
        "name": "browser_press_key",
        "description": "Press a keyboard key (useful for Tab, Enter, Escape, etc.)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "key": {
                    "type": "STRING",
                    "description": "Key to press (e.g., 'Enter', 'Tab', 'Escape', 'ArrowDown')"
                }
            },
            "required": ["key"]
        }
    },
    {
        "name": "browser_get_url",
        "description": "Get the current page URL (useful to verify navigation)",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "browser_dom_snapshot",
        "description": "Get a concise DOM snapshot with interactive elements and accessibility tree",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "finish_exploration",
        "description": "Signal that exploration is complete and ready for final evaluation",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "STRING",
                    "description": "Brief summary of what was tested"
                }
            },
            "required": ["summary"]
        }
    }
]


class AgenticEvaluator(GeminiEvaluator):
    """
    Agentic evaluator where Gemini directly controls browser through MCP tools
    
    Flow:
    1. Load page and inject dialog detection
    2. Observe→Act loop: Get state (with screenshot image) → Gemini picks action → Execute → Verify → Repeat
    3. After N steps or "finish_exploration", run final vision evaluation
    
    Improvements:
    - Sends PIL.Image screenshots to Gemini (truly multimodal)
    - Captures before/after verification signals
    - Detects system dialogs
    - Better interactive element discovery with stable selectors
    - Comprehensive artifacts saved per step
    """
    
    def __init__(self, max_exploration_steps: int = 50):
        super().__init__()
        self.max_exploration_steps = max_exploration_steps
        self.exploration_log = []
        self.step_artifacts = []  # Per-step artifact metadata
        
        # Configure Gemini with function calling
        # Use EVALUATOR_MODEL env var, fallback to gemini-3-flash-preview for stability
        agent_model_name = os.getenv("EVALUATOR_MODEL", "gemini-3-flash-preview")
        logger.info(f"Using agent model: {agent_model_name}")
        
        self.agent_model = genai.GenerativeModel(
            model_name=agent_model_name,
            tools=BROWSER_TOOLS
        )
        
        logger.info(f"Agentic evaluator initialized (max steps: {max_exploration_steps})")
    
    async def evaluate(
        self,
        url: str,
        mcp_client,
        task: str,
        screenshots_dir: Path,
        rubric: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate page (compatible with GeminiEvaluator interface)
        
        This is a wrapper that calls evaluate_page with the correct parameters.
        """
        return await self.evaluate_page(
            url=url,
            mcp_client=mcp_client,
            task=task,
            artifacts_dir=screenshots_dir,
            rubric=rubric
        )
    
    async def evaluate_page(
        self,
        url: str,
        mcp_client,
        task: str,
        artifacts_dir: Path,
        rubric: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate page with agentic browser control
        
        Args:
            url: Page URL (HTTP only)
            mcp_client: MCP client for browser control
            task: Original task description
            artifacts_dir: Directory to save artifacts
            rubric: Optional custom rubric
        
        Returns:
            EvaluationResult with autonomous exploration + vision scoring
        """
        
        logger.info("=" * 70)
        logger.info("🤖 AGENTIC EVALUATION - Gemini Controls Browser")
        logger.info("=" * 70)
        logger.info(f"Task: {task}")
        logger.info(f"URL: {url}")
        logger.info(f"Max steps: {self.max_exploration_steps}")
        logger.info("=" * 70)
        
        rubric = rubric or EVALUATION_RUBRIC
        
        # Start video recording
        video_path = str(artifacts_dir / "evaluation_recording.webm")
        logger.info(f"\n🎥 Starting video recording: {video_path}")
        try:
            await mcp_client.start_recording(video_path)
            logger.info("✅ Video recording started")
        except Exception as e:
            logger.warning(f"⚠️  Failed to start video recording: {e}")
            video_path = None
        
        try:
            # Phase 1: Navigate to page and inject dialog detection
            logger.info("\n📍 Phase 1: Navigate to page and setup")
            await mcp_client.navigate(url)
            await asyncio.sleep(2)  # Let page load
            
            # Inject dialog detection early
            await self._inject_dialog_detection(mcp_client)
            
            # Phase 2: Agentic exploration (observe→act loop)
            logger.info("\n🔍 Phase 2: Agentic Exploration")
            exploration_result = await self._run_exploration_loop(
                mcp_client, 
                task,
                artifacts_dir
            )
            
            # Phase 3: Check single-file compliance
            logger.info("\n📋 Phase 3a: Checking Single-File Compliance")
            file_compliance = await self._check_single_file_compliance(mcp_client)
            
            if file_compliance.get('compliant') is False:
                logger.warning("❌ VIOLATION: External CSS/JS files detected!")
                logger.warning(f"   External CSS: {file_compliance.get('external_css_count', 0)}")
                logger.warning(f"   External JS: {file_compliance.get('external_js_count', 0)}")
            elif file_compliance.get('compliant') is True:
                logger.info("✅ Single-file compliance verified")
            
            # Check template structure compliance
            logger.info("\n🔍 Checking template structure compliance...")
            template_compliance = await self._check_template_structure_compliance(mcp_client)
            logger.info(f"   Template compliance: {template_compliance.get('template_compliant', 'unknown')}")
            if template_compliance.get('is_simple_quiz'):
                logger.warning("   ⚠️  Page appears to be a simple quiz, not using template structure!")
            
            # Phase 3: Final vision evaluation
            logger.info("\n👁️  Phase 3b: Final Vision Evaluation")
            final_eval = await self._run_vision_evaluation(
                task,
                exploration_result["final_observation"],
                rubric,
                exploration_result,
                file_compliance,
                template_compliance
            )
        finally:
            # Stop video recording
            if video_path:
                logger.info(f"\n🎥 Stopping video recording...")
                try:
                    saved_path = await mcp_client.stop_recording()
                    if saved_path:
                        logger.info(f"✅ Video saved: {saved_path}")
                        # Update exploration result with video path
                        exploration_result["video_path"] = saved_path
                    else:
                        logger.warning("⚠️  Video recording stopped but path not returned")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to stop video recording: {e}")
        
        # Save exploration log
        log_file = artifacts_dir / "agentic_exploration.json"
        log_file.write_text(json.dumps({
            "exploration_steps": self.exploration_log,
            "total_steps": exploration_result["steps_taken"],
            "completion_reason": exploration_result["completion_reason"],
            "final_evaluation": asdict(final_eval)
        }, indent=2))
        
        logger.info(f"\n✅ Agentic evaluation complete")
        logger.info(f"   Steps taken: {exploration_result['steps_taken']}")
        logger.info(f"   Final score: {final_eval.score}/100")
        logger.info(f"   Exploration log: {log_file}")
        
        return final_eval
    
    def _safe_extract_response_parts(self, response) -> Dict[str, Any]:
        """
        Safely extract tool calls and text from Gemini response
        
        Handles:
        - Empty candidates list
        - Missing content/parts
        - Multiple function calls
        - Text-only responses
        
        Returns:
            {
                "function_calls": List[function_call objects],
                "reasoning": str (concatenated text),
                "has_content": bool
            }
        """
        result = {
            "function_calls": [],
            "reasoning": "",
            "has_content": False
        }
        
        if not response or not hasattr(response, 'candidates'):
            logger.warning("⚠️  Response has no candidates attribute")
            return result
        
        if not response.candidates or len(response.candidates) == 0:
            logger.warning("⚠️  Empty candidates list from Gemini")
            return result
        
        candidate = response.candidates[0]
        
        if not candidate.content or not candidate.content.parts:
            logger.warning("⚠️  Candidate has no content or parts")
            return result
        
        # Extract all parts
        for part in candidate.content.parts:
            if hasattr(part, 'text') and part.text:
                result["reasoning"] += part.text
                result["has_content"] = True
            if hasattr(part, 'function_call') and part.function_call:
                result["function_calls"].append(part.function_call)
                result["has_content"] = True
        
        return result
    
    async def _run_exploration_loop(
        self,
        mcp_client,
        task: str,
        artifacts_dir: Path
    ) -> Dict[str, Any]:
        """
        Run observe→act loop where Gemini chooses actions (MULTIMODAL)
        
        Key improvements:
        - Sends PIL.Image screenshots to Gemini each step
        - Captures before/after verification signals
        - Robust function call parsing (handles multiple parts)
        - Saves comprehensive per-step artifacts
        - Soft recovery from model failures
        
        Returns:
            Dict with exploration results and final observation
        """
        
        # Build system prompt for agent
        agent_prompt = self._build_agent_prompt(task)
        
        # Start conversation
        chat = self.agent_model.start_chat()
        
        steps_taken = 0
        finished = False
        final_observation = None
        consecutive_failures = 0  # Track failures for soft recovery
        
        for step in range(self.max_exploration_steps):
            steps_taken += 1
            
            logger.info(f"\n{'─' * 70}")
            logger.info(f"Step {step + 1}/{self.max_exploration_steps}")
            logger.info(f"{'─' * 70}")
            
            # Observe: Get current browser state with screenshot (BEFORE action)
            logger.info("📸 Observing browser state (BEFORE)...")
            before_state = await self._get_browser_state(mcp_client, artifacts_dir, step, phase="before")
            
            # Build observation message for Gemini (textual part)
            observation_msg = self._format_observation(before_state, step)
            
            # Act: Let Gemini choose next action (MULTIMODAL: send text + image)
            logger.info("🤔 Gemini choosing next action...")
            
            try:
                # Build multimodal content: text + screenshot image
                content_parts = []
                
                if step == 0:
                    # First step: include system prompt
                    content_parts.append(f"{agent_prompt}\n\n{observation_msg}")
                else:
                    content_parts.append(observation_msg)
                
                # Add screenshot image if available
                screenshot_path = before_state.get("screenshot_path")
                if screenshot_path and Path(screenshot_path).exists():
                    try:
                        img = PIL.Image.open(screenshot_path)
                        content_parts.append(img)
                        logger.info(f"   📷 Included screenshot in observation")
                    except Exception as e:
                        logger.warning(f"Failed to load screenshot: {e}")
                
                # Send multimodal message
                response = chat.send_message(content_parts)
                
                # Parse response safely
                parsed = self._safe_extract_response_parts(response)
                reasoning_text = parsed["reasoning"]
                function_calls = parsed["function_calls"]
                
                if reasoning_text:
                    logger.info(f"   💭 Reasoning: {reasoning_text[:150]}")
                
                # Handle empty response (soft recovery)
                if not parsed["has_content"]:
                    consecutive_failures += 1
                    logger.warning(f"⚠️  Empty response from Gemini (failure {consecutive_failures}/3)")
                    
                    if consecutive_failures >= 3:
                        logger.error("❌ Too many empty responses, ending exploration")
                        final_observation = before_state
                        break
                    
                    # Take safe default action: scroll down
                    logger.info("   🔄 Soft recovery: scrolling down to gather more context")
                    await self._execute_tool("browser_scroll", {"direction": "down", "amount": 500}, mcp_client)
                    await asyncio.sleep(1)
                    continue
                
                # Reset failure counter on success
                consecutive_failures = 0
                
                if function_calls:
                    # Gemini expects responses for ALL function calls
                    if len(function_calls) > 1:
                        logger.warning(f"⚠️  Multiple function calls detected ({len(function_calls)}), will execute all")
                    
                    # For now, only execute first but log all
                    func_call = function_calls[0]
                    args_dict = dict(func_call.args) if func_call.args else {}
                    
                    logger.info(f"🔧 Tool call: {func_call.name} (1 of {len(function_calls)})")
                    logger.info(f"   Args: {args_dict}")
                    
                    # Check for finish signal
                    if func_call.name == "finish_exploration":
                        logger.info(f"✅ Gemini finished exploration")
                        logger.info(f"   Summary: {args_dict.get('summary', 'N/A')}")
                        
                        # Log the step
                        step_log = {
                            "step": step + 1,
                            "tool": func_call.name,
                            "args": args_dict,
                            "reasoning": reasoning_text,
                            "before_state": self._compact_state(before_state),
                        }
                        self.exploration_log.append(step_log)
                        
                        finished = True
                        final_observation = before_state
                        break
                    
                    # Execute browser action and verify
                    tool_result = await self._execute_tool(
                        func_call.name,
                        args_dict,
                        mcp_client
                    )
                    
                    logger.info(f"   Result: {tool_result.get('success', False)}")
                    
                    # Wait a moment after action
                    await asyncio.sleep(0.5)
                    
                    # Get AFTER state for verification
                    logger.info("📸 Capturing AFTER state...")
                    after_state = await self._get_browser_state(mcp_client, artifacts_dir, step, phase="after")
                    
                    # Compute verification signals
                    verification = self._compute_verification(before_state, after_state)
                    logger.info(f"   🔍 Verification: DOM changed={verification['dom_changed']}, "
                               f"text_changed={verification['text_changed']}, "
                               f"dialogs={len(verification['dialogs'])}")
                    
                    # Log the step with full context
                    step_log = {
                        "step": step + 1,
                        "tool": func_call.name,
                        "args": args_dict,
                        "reasoning": reasoning_text,
                        "tool_result": tool_result,
                        "before_state": self._compact_state(before_state),
                        "after_state": self._compact_state(after_state),
                        "verification": verification
                    }
                    self.exploration_log.append(step_log)
                    
                    # Save step artifacts
                    step_artifact = {
                        "step": step + 1,
                        "before_screenshot": before_state.get("screenshot_path"),
                        "after_screenshot": after_state.get("screenshot_path"),
                        "observation_file": str(artifacts_dir / f"step_{step + 1}_observation.json")
                    }
                    self.step_artifacts.append(step_artifact)
                    
                    # Save observation JSON
                    observation_file = Path(step_artifact["observation_file"])
                    observation_file.write_text(json.dumps({
                        "text_visible": before_state.get("visible_text", "")[:1000],
                        "interactive_targets": before_state.get("interactive_targets", [])[:20],
                        "console_errors": before_state.get("console_errors", []),
                        "verification": verification
                    }, indent=2))
                    
                    # Send tool result back to Gemini with verification info
                    # Keep response simple and JSON-serializable
                    response_data = {
                        "success": bool(tool_result.get("success", False)),
                        "message": str(tool_result.get("message", "")),
                        "dom_changed": bool(verification["dom_changed"]),
                        "text_changed": bool(verification["text_changed"]),
                        "new_errors": int(len(verification["new_console_errors"]))
                    }
                    
                    # Create function response parts for ALL function calls
                    # (even if we only executed the first one)
                    response_parts = []
                    for i, fc in enumerate(function_calls):
                        if i == 0:
                            # Use actual result for first call
                            response_parts.append(
                                genai.protos.Part(function_response=genai.protos.FunctionResponse(
                                    name=fc.name,
                                    response={"result": json.dumps(response_data)}
                                ))
                            )
                        else:
                            # Send "not executed" for additional calls
                            response_parts.append(
                                genai.protos.Part(function_response=genai.protos.FunctionResponse(
                                    name=fc.name,
                                    response={"result": json.dumps({"success": False, "message": "Only first function call executed per turn"})}
                                ))
                            )
                    
                    # Send function response with retry
                    try:
                        chat.send_message(genai.protos.Content(parts=response_parts))
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to send function response (attempt 1): {e}")
                        # Retry once with minimal payload
                        try:
                            simple_response = genai.protos.Content(parts=[
                                genai.protos.Part(function_response=genai.protos.FunctionResponse(
                                    name=function_calls[0].name,
                                    response={"result": "executed"}
                                ))
                            ])
                            chat.send_message(simple_response)
                            logger.info("   ✅ Retry succeeded with simple response")
                        except Exception as e2:
                            logger.error(f"❌ Failed to send function response (attempt 2): {e2}")
                            # Don't crash, just continue with next step
                            consecutive_failures += 1
                            if consecutive_failures >= 3:
                                logger.error("❌ Too many response send failures, ending exploration")
                                final_observation = after_state
                                break
                else:
                    logger.warning("⚠️  No function call in response")
                    logger.info(f"   Reasoning text: {reasoning_text[:300]}")
                    # Take safe default action
                    logger.info("   🔄 Soft recovery: taking snapshot for context")
                    await self._execute_tool("browser_dom_snapshot", {}, mcp_client)
                
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"❌ Error in exploration step (failure {consecutive_failures}/3): {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                if consecutive_failures >= 3:
                    logger.error("❌ Too many consecutive failures, ending exploration")
                    break
                
                # Soft recovery: continue to next step
                logger.info("   🔄 Soft recovery: continuing to next step")
                await asyncio.sleep(1)
        
        if not finished:
            logger.info(f"\n⏱️  Reached max exploration steps ({self.max_exploration_steps}) - this is normal, not an error")
            logger.info(f"   The evaluator has completed {steps_taken} exploration steps and will now perform final evaluation")
            # Get final state
            final_observation = await self._get_browser_state(mcp_client, artifacts_dir, step, phase="final")
        
        return {
            "steps_taken": steps_taken,
            "completion_reason": "agent_finished" if finished else "max_steps_reached",
            "final_observation": final_observation
        }
    
    def _build_agent_prompt(self, task: str) -> str:
        """Build system prompt for agentic exploration"""
        
        return f"""You are an autonomous browser testing agent with VISION. You can see screenshots of the page and must THOROUGHLY test everything.

**Task Description:**
{task}

**Your Mission - BE THOROUGH AND FAIR:**
1. You will receive screenshots showing the actual rendered page
2. Test EVERY interactive element listed in the task requirements
3. After EACH action, you'll receive verification signals showing if the page changed
4. Use your vision to confirm things work: buttons respond, content appears, UI updates
5. Be harsh only when you have EVIDENCE something is broken (you had a chance to verify and it failed)
6. Test systematically: scroll, read, interact, verify, repeat

**Available Tools:**
- browser_click: Click elements (use selectors from the interactive elements list)
  **NOTE:** Do NOT try to click disabled buttons (they're greyed out for a reason - e.g., prev disabled on first module, next disabled on last module)
- browser_type: Type into input fields
- browser_scroll: Scroll up/down to see all content
- browser_evaluate: Execute JavaScript to check state, get values
- browser_wait_for: Wait for elements/text to appear (selector or text, optional timeout in ms)
- browser_hover: Hover over elements to reveal tooltips/effects
- browser_press_key: Press keyboard keys (Enter, Tab, Escape, etc.)
- browser_get_url: Get current page URL (verify navigation)
- browser_dom_snapshot: Get detailed interactive element list
- finish_exploration: Signal done (include detailed summary of findings)

**Testing Strategy:**
1. OBSERVE: Look at the screenshot, read visible text, check interactive elements list
2. ACT: Choose a relevant action (click button, type input, scroll, etc.)
3. VERIFY: After action, check verification signals:
   - Did DOM change?
   - Did visible text change?
   - New console errors?
   - Dialogs detected?
4. DOCUMENT: Note what works and what doesn't
5. REPEAT: Continue until all features tested

**Evaluation Policy - Harsh but Fair:**
- ✅ Feature works if: You interacted AND saw expected changes (visual/DOM/text)
- ❌ Feature broken if: You tried reasonable interactions AND nothing happened OR errors appeared
- ⚠️ Feature untestable if: You couldn't interact (element not found, crashes)
- Dialog detection: System dialogs (alert/confirm/prompt) are logged and indicate poor UX
- Console errors: Count as robustness failures

**When to Finish:**
- Test every feature mentioned in the task
- Verify each interactive element
- Scroll entire page
- Try edge cases if time permits
- Then call finish_exploration with:
  - What you tested
  - What works (with evidence)
  - What fails (with evidence)
  - What you couldn't test (with reasons)

Begin systematic testing. You have vision - use it!"""
    
    def _format_observation(self, state: Dict[str, Any], step: int) -> str:
        """
        Format browser state as observation message for Gemini
        
        Includes: text snippet, interactive targets with selectors, console errors, dialogs
        """
        
        obs = f"**Step {step + 1} Observation:**\n\n"
        
        # URL
        if state.get("current_url"):
            obs += f"**Current URL:** {state['current_url']}\n\n"
        
        # Visible text snippet
        text_snippet = state.get("text_snippet", "")
        if text_snippet:
            obs += f"**Visible Text (first 800 chars):**\n{text_snippet[:800]}\n\n"
        
        # Interactive targets with stable selectors
        targets = state.get("interactive_targets", [])
        if targets:
            obs += f"**Interactive Elements ({len(targets)} found, showing top 15):**\n"
            for i, target in enumerate(targets[:15], 1):
                selector = target.get("selector", "unknown")
                text = target.get("text", "")
                role = target.get("role", "")
                text_display = f": {text[:50]}" if text else ""
                obs += f"  {i}. {selector} [{role}]{text_display}\n"
            obs += "\n"
        else:
            obs += "**Interactive Elements:** None found\n\n"
        
        # Console errors
        errors = state.get("console_errors", [])
        if errors:
            obs += f"**Console Errors:** {len(errors)} detected\n"
            for err in errors[:3]:
                obs += f"  - {err.get('text', str(err))[:100]}\n"
            obs += "\n"
        else:
            obs += "**Console Errors:** None\n\n"
        
        # Dialogs detected
        dialogs = state.get("dialogs", [])
        if dialogs:
            obs += f"**⚠️ DIALOGS DETECTED:** {len(dialogs)}\n"
            for d in dialogs[-3:]:
                obs += f"  - {d.get('type')}: {d.get('message', '')[:80]}\n"
            obs += "\n"
        
        obs += "**What action should we take next?** Use a tool to continue exploration or call finish_exploration when done."
        
        return obs
    
    async def _get_browser_state(
        self,
        mcp_client,
        artifacts_dir: Path,
        step: int,
        phase: str = "before"
    ) -> Dict[str, Any]:
        """
        Get comprehensive browser state with verification signals
        
        Args:
            mcp_client: Browser client
            artifacts_dir: Where to save artifacts
            step: Current step number
            phase: "before", "after", or "final"
        
        Returns:
            State dict with screenshot, text, targets, console errors, DOM signature, dialogs
        """
        
        state = {}
        
        # Take screenshot
        screenshot_filename = f"step_{step + 1}_{phase}.png"
        screenshot_path = artifacts_dir / screenshot_filename
        await mcp_client.screenshot(str(screenshot_path))
        state["screenshot_path"] = str(screenshot_path)
        
        # Get page visible text - ROBUST: handle non-string returns
        try:
            text_js = "document.body.innerText"
            result = await mcp_client.evaluate(text_js)
            visible_text_raw = result.get("result", "")
            
            # Defensive: coerce to string safely
            if isinstance(visible_text_raw, str):
                visible_text = visible_text_raw
            elif isinstance(visible_text_raw, (list, tuple)):
                visible_text = " ".join(str(x) for x in visible_text_raw[:50])  # Join first 50 items
            elif isinstance(visible_text_raw, dict):
                visible_text = json.dumps(visible_text_raw, default=str)[:2000]  # Truncate JSON
            elif visible_text_raw is None:
                visible_text = ""
            else:
                visible_text = str(visible_text_raw)
                logger.debug(f"Unexpected visible_text type: {type(visible_text_raw)}, coerced to string")
            
            state["visible_text"] = visible_text
            state["text_snippet"] = visible_text[:1500] if visible_text else ""
        except Exception as e:
            logger.warning(f"Failed to get visible text: {e}")
            state["visible_text"] = ""
            state["text_snippet"] = ""
        
        # Get interactive targets with stable selectors
        try:
            state["interactive_targets"] = await self._discover_interactive_targets(mcp_client)
        except Exception as e:
            logger.warning(f"Failed to discover interactive targets: {e}")
            state["interactive_targets"] = []
        
        # Get console errors
        try:
            messages = await mcp_client.get_console()
            state["console_errors"] = [
                {"level": m.get("level"), "text": m.get("text", "")}
                for m in messages 
                if m.get("level") == "error"
            ]
        except Exception as e:
            logger.warning(f"Failed to get console: {e}")
            state["console_errors"] = []
        
        # Compute DOM change signature (for verification)
        try:
            state["dom_signature"] = await self._compute_dom_signature(mcp_client)
        except Exception as e:
            logger.warning(f"Failed to compute DOM signature: {e}")
            state["dom_signature"] = ""
        
        # Check for dialogs
        try:
            state["dialogs"] = await self._get_dialog_calls(mcp_client)
        except Exception as e:
            logger.warning(f"Failed to get dialogs: {e}")
            state["dialogs"] = []
        
        # Get current URL
        try:
            url_js = "window.location.href"
            result = await mcp_client.evaluate(url_js)
            state["current_url"] = result.get("result", "")
        except:
            state["current_url"] = ""
        
        return state
    
    async def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        mcp_client
    ) -> Dict[str, Any]:
        """
        Execute a browser tool and return structured result
        
        Supports expanded toolset including wait_for, hover, press_key, etc.
        """
        
        try:
            if tool_name == "browser_click":
                selector = args["selector"]
                # Try MCP tool first, fallback to JS if not available
                try:
                    result = await mcp_client.call_tool("browser_click", {"selector": selector})
                    success = result.get("success", False)
                    return {"success": success, "message": f"Clicked {selector}" if success else f"Element not found: {selector}"}
                except Exception as e:
                    # Fallback: click via JS
                    logger.debug(f"MCP click failed, using JS fallback: {e}")
                    click_js = f"""
                    (function() {{
                        const el = document.querySelector({json.dumps(selector)});
                        if (el) {{
                            el.click();
                            return true;
                        }}
                        return false;
                    }})()
                    """
                    result = await mcp_client.evaluate(click_js)
                    success = result.get("result", False)
                    return {"success": success, "message": f"Clicked {selector}" if success else f"Element not found: {selector}"}
            
            elif tool_name == "browser_type":
                selector = args["selector"]
                text = args["text"]
                # Try MCP tool first, fallback to JS if not available
                try:
                    result = await mcp_client.call_tool("browser_type", {"selector": selector, "text": text})
                    success = result.get("success", False)
                    return {"success": success, "message": f"Typed '{text}' into {selector}" if success else f"Element not found: {selector}"}
                except Exception as e:
                    # Fallback: type via JS
                    logger.debug(f"MCP type failed, using JS fallback: {e}")
                    type_js = f"""
                    (function() {{
                        const el = document.querySelector({json.dumps(selector)});
                        if (el) {{
                            el.value = {json.dumps(text)};
                            el.dispatchEvent(new Event('input', {{bubbles: true}}));
                            el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }}
                        return false;
                    }})()
                    """
                    result = await mcp_client.evaluate(type_js)
                    success = result.get("result", False)
                    return {"success": success, "message": f"Typed '{text}' into {selector}" if success else f"Element not found: {selector}"}
            
            elif tool_name == "browser_scroll":
                direction = args["direction"]
                amount = args.get("amount", 500)
                scroll_js = f"window.scrollBy(0, {amount if direction == 'down' else -amount})"
                await mcp_client.evaluate(scroll_js)
                return {"success": True, "message": f"Scrolled {direction} {amount}px"}
            
            elif tool_name == "browser_evaluate":
                result = await mcp_client.evaluate(args["expression"])
                return {"success": True, "result": result.get("result")}
            
            elif tool_name == "browser_wait_for":
                selector = args.get("selector")
                text = args.get("text")
                timeout = args.get("timeout", 3000)
                
                # Simple wait implementation via polling
                if selector:
                    wait_js = f"""
                    (function() {{
                        const el = document.querySelector({json.dumps(selector)});
                        return el !== null;
                    }})()
                    """
                    result = await mcp_client.evaluate(wait_js)
                    if result.get("result"):
                        return {"success": True, "message": f"Element {selector} found"}
                    else:
                        await asyncio.sleep(timeout / 1000)
                        return {"success": False, "message": f"Element {selector} not found after {timeout}ms"}
                elif text:
                    # Wait for text
                    await asyncio.sleep(timeout / 1000)
                    text_js = "document.body.innerText"
                    result = await mcp_client.evaluate(text_js)
                    body_text = result.get("result", "")
                    found = text in body_text
                    return {"success": found, "message": f"Text '{text}' {'found' if found else 'not found'}"}
                else:
                    # Just wait
                    await asyncio.sleep(timeout / 1000)
                    return {"success": True, "message": f"Waited {timeout}ms"}
            
            elif tool_name == "browser_hover":
                selector = args["selector"]
                hover_js = f"""
                (function() {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (el) {{
                        el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
                        el.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }})()
                """
                result = await mcp_client.evaluate(hover_js)
                success = result.get("result", False)
                return {"success": success, "message": f"Hovered {selector}"}
            
            elif tool_name == "browser_press_key":
                key = args["key"]
                press_js = f"""
                (function() {{
                    document.dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, bubbles: true}}));
                    document.dispatchEvent(new KeyboardEvent('keyup', {{key: {json.dumps(key)}, bubbles: true}}));
                    return true;
                }})()
                """
                await mcp_client.evaluate(press_js)
                return {"success": True, "message": f"Pressed key: {key}"}
            
            elif tool_name == "browser_get_url":
                url_js = "window.location.href"
                result = await mcp_client.evaluate(url_js)
                url = result.get("result", "")
                return {"success": True, "url": url, "message": f"Current URL: {url}"}
            
            elif tool_name == "browser_dom_snapshot":
                # Return concise DOM snapshot
                targets = await self._discover_interactive_targets(mcp_client)
                return {
                    "success": True,
                    "interactive_elements": targets[:30],
                    "message": f"Found {len(targets)} interactive elements"
                }
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _run_vision_evaluation(
        self,
        task: str,
        final_observation: Dict[str, Any],
        rubric: Dict[str, Any],
        exploration_result: Dict[str, Any],
        file_compliance: Dict[str, Any] = None,
        template_compliance: Dict[str, Any] = None
    ) -> EvaluationResult:
        """
        Run final vision evaluation using the original GeminiEvaluator logic
        
        Args:
            task: Original task
            final_observation: Final browser state from exploration
            rubric: Evaluation rubric
            exploration_result: Full exploration results
        
        Returns:
            EvaluationResult
        """
        
        # Convert exploration data to BrowserObservation format
        observation = BrowserObservation(
            desktop_screenshot=final_observation.get("screenshot_path"),
            console_errors=final_observation.get("console_errors", []),
            interactions_performed=[
                f"{step['tool']}({step['args']})"
                for step in self.exploration_log
            ]
        )
        
        # Build evaluation prompt
        prompt = self._build_vision_prompt(task, observation, rubric, exploration_result, file_compliance, template_compliance)
        
        # Call Gemini for final scoring WITH SCREENSHOTS
        model = genai.GenerativeModel(
            model_name=os.getenv("EVALUATOR_MODEL", "gemini-3-flash-preview")
        )
        
        # Include screenshots from exploration
        content_parts = [prompt]
        
        # Add screenshots from key steps (first, middle, last)
        screenshot_steps = []
        if len(self.exploration_log) > 0:
            screenshot_steps.append(0)  # First
        if len(self.exploration_log) > 2:
            screenshot_steps.append(len(self.exploration_log) // 2)  # Middle
        if len(self.exploration_log) > 1:
            screenshot_steps.append(len(self.exploration_log) - 1)  # Last
        
        for idx in screenshot_steps:
            screenshot_path = self.exploration_log[idx].get('screenshot')
            if screenshot_path and Path(screenshot_path).exists():
                try:
                    import PIL.Image
                    img = PIL.Image.open(screenshot_path)
                    content_parts.append(f"\n[Screenshot from step {idx + 1}]")
                    content_parts.append(img)
                except Exception as e:
                    logger.warning(f"Failed to load screenshot {screenshot_path}: {e}")
        
        response = model.generate_content(content_parts)
        
        # Parse response
        eval_result = self._parse_evaluation_response(response.text)
        
        return eval_result
    
    async def _check_single_file_compliance(self, mcp_client) -> Dict[str, Any]:
        """
        Check if the page uses inline CSS/JS (single-file compliance)
        
        Returns:
            Dict with compliance status and details
        """
        try:
            # Check for external CSS files
            css_check = """
            (function() {
                const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
                return {
                    external_css_count: links.length,
                    external_css_hrefs: links.map(l => l.href),
                    has_inline_style: document.querySelector('style') !== null
                };
            })()
            """
            
            # Check for external JS files
            js_check = """
            (function() {
                const scripts = Array.from(document.querySelectorAll('script[src]'));
                return {
                    external_js_count: scripts.length,
                    external_js_srcs: scripts.map(s => s.src),
                    has_inline_script: Array.from(document.querySelectorAll('script')).some(s => !s.src && s.textContent.trim().length > 0)
                };
            })()
            """
            
            css_result = await mcp_client.evaluate(css_check)
            js_result = await mcp_client.evaluate(js_check)
            
            css_data = css_result.get('result', {})
            js_data = js_result.get('result', {})
            
            external_css = css_data.get('external_css_count', 0)
            external_js = js_data.get('external_js_count', 0)
            has_inline_css = css_data.get('has_inline_style', False)
            has_inline_js = js_data.get('has_inline_script', False)
            
            is_compliant = external_css == 0 and external_js == 0
            
            return {
                'compliant': is_compliant,
                'external_css_count': external_css,
                'external_js_count': external_js,
                'has_inline_css': has_inline_css,
                'has_inline_js': has_inline_js,
                'external_css_files': css_data.get('external_css_hrefs', []),
                'external_js_files': js_data.get('external_js_srcs', [])
            }
        except Exception as e:
            logger.warning(f"Failed to check single-file compliance: {e}")
            return {
                'compliant': None,
                'error': str(e)
            }
    
    async def _check_template_structure_compliance(self, mcp_client) -> Dict[str, Any]:
        """
        Check if the page uses the template structure (module navigation, audio controls, etc.)
        
        Returns:
            Dict with template compliance status and details
        """
        try:
            template_check = """
            (function() {
                // Check for template structure components
                const has_module_selector = document.querySelector('select[id*="module"], select[id*="selector"], select[class*="module"]') !== null;
                const has_prev_next = document.querySelector('button[id*="prev"], button[id*="next"], button[class*="prev"], button[class*="next"]') !== null;
                const has_progress_indicator = document.body.innerText.includes(' of ') || document.body.innerText.match(/\\d+\\s+of\\s+\\d+/);
                
                // Check for audio controls (microphone icons, audio buttons)
                const audio_controls = Array.from(document.querySelectorAll('button[class*="audio"], button[aria-label*="audio"], button[aria-label*="play"], svg[class*="audio"], .audio-control'));
                const has_audio_controls = audio_controls.length > 0;
                
                // Check for notes panel/button
                const notes_button = document.querySelector('button[id*="notes"], button[class*="notes"], button[aria-label*="notes"]');
                const has_notes = notes_button !== null;
                
                // Check for chatbot button
                const chatbot_button = document.querySelector('button[id*="chatbot"], button[id*="chat"], button[class*="chatbot"], button[class*="chat"], button[aria-label*="chat"]');
                const has_chatbot = chatbot_button !== null;
                
                // Check for modules array in JavaScript
                const scripts = Array.from(document.querySelectorAll('script'));
                let has_modules_array = false;
                let modules_count = 0;
                for (const script of scripts) {
                    const text = script.textContent || '';
                    if (text.includes('modules') && (text.includes('let modules') || text.includes('const modules') || text.includes('var modules'))) {
                        has_modules_array = true;
                        // Try to extract module count
                        const match = text.match(/modules\\s*=\\s*\\[([^\\]]*)\\]/);
                        if (match) {
                            modules_count = (match[1].match(/\\{[^}]*\\}/g) || []).length;
                        }
                    }
                }
                
                // Check for template sections
                const has_video_section = document.querySelector('iframe[src*="youtube"], iframe[src*="youtu.be"], [id*="video"], [class*="video"]') !== null;
                const has_explanation = document.querySelector('[id*="explanation"], [class*="explanation"]') !== null;
                const has_key_points = document.querySelector('[id*="key"], [class*="key-point"], ul, ol') !== null;
                const has_timeline = document.querySelector('[id*="timeline"], [class*="timeline"]') !== null;
                const has_fun_fact = document.querySelector('[id*="fun"], [class*="fun-fact"], [class*="funfact"]') !== null;
                
                // Check if it's just a simple quiz (no template structure)
                const is_simple_quiz = !has_module_selector && !has_prev_next && !has_audio_controls && !has_notes && !has_chatbot && !has_modules_array;
                
                return {
                    has_module_navigation: has_module_selector || has_prev_next,
                    has_progress_indicator: has_progress_indicator,
                    has_audio_controls: has_audio_controls,
                    audio_controls_count: audio_controls.length,
                    has_notes_panel: has_notes,
                    has_chatbot: has_chatbot,
                    has_modules_array: has_modules_array,
                    modules_count: modules_count,
                    has_video_section: has_video_section,
                    has_explanation_section: has_explanation,
                    has_key_points_section: has_key_points,
                    has_timeline_section: has_timeline,
                    has_fun_fact_section: has_fun_fact,
                    is_simple_quiz: is_simple_quiz,
                    template_compliant: has_module_selector && has_audio_controls && has_modules_array
                };
            })()
            """
            
            result = await mcp_client.evaluate(template_check)
            template_data = result.get('result', {})
            
            return template_data
        except Exception as e:
            logger.warning(f"Failed to check template structure: {e}")
            return {
                'template_compliant': None,
                'error': str(e)
            }
    
    def _build_vision_prompt(
        self,
        task: str,
        observation: BrowserObservation,
        rubric: Dict[str, Any],
        exploration: Dict[str, Any],
        file_compliance: Dict[str, Any] = None,
        template_compliance: Dict[str, Any] = None
    ) -> str:
        """Build prompt for final vision evaluation with correct rubric weights"""
        
        # Add file compliance check results
        compliance_section = ""
        if file_compliance:
            if file_compliance.get('compliant') is False:
                compliance_section = f"""
**❌ CRITICAL VIOLATION - Single-File Requirement:**
- External CSS files found: {file_compliance.get('external_css_count', 0)}
- External JS files found: {file_compliance.get('external_js_count', 0)}
- External files: {', '.join(file_compliance.get('external_css_files', []) + file_compliance.get('external_js_files', []))}
**THIS IS A CRITICAL FAILURE - The requirement is for ALL CSS/JS to be INLINE in the HTML file.**
**Score must be heavily penalized (deduct at least 30 points) for this violation.**
"""
            elif file_compliance.get('compliant') is True:
                compliance_section = "\n**✅ Single-File Compliance: Verified - All CSS/JS are inline**\n"
        
        # Add template structure compliance check results
        template_section = ""
        if template_compliance:
            if template_compliance.get('is_simple_quiz'):
                template_section = f"""
**❌ CRITICAL VIOLATION - Template Structure Missing:**
The page appears to be a simple quiz page, NOT using the required template structure.

**Missing Template Components:**
- Module navigation: {template_compliance.get('has_module_navigation', False)}
- Audio controls: {template_compliance.get('has_audio_controls', False)} (found {template_compliance.get('audio_controls_count', 0)} controls)
- Notes panel: {template_compliance.get('has_notes_panel', False)}
- Chatbot: {template_compliance.get('has_chatbot', False)}
- Modules array: {template_compliance.get('has_modules_array', False)} (modules count: {template_compliance.get('modules_count', 0)})
- Video section: {template_compliance.get('has_video_section', False)}
- Explanation section: {template_compliance.get('has_explanation_section', False)}
- Key points section: {template_compliance.get('has_key_points_section', False)}
- Timeline section: {template_compliance.get('has_timeline_section', False)}
- Fun fact section: {template_compliance.get('has_fun_fact_section', False)}

**THIS IS A CRITICAL FAILURE - The page must use the template structure with module navigation, audio controls, notes panel, chatbot, and multiple modules.**
**A simple quiz page does NOT meet the requirements.**
**Score must be heavily penalized (deduct at least 40 points) for missing template structure.**
**The page should have been built using template.html as the starting point.**
"""
            elif not template_compliance.get('template_compliant', True):
                missing = []
                if not template_compliance.get('has_module_navigation'): missing.append("module navigation")
                if not template_compliance.get('has_audio_controls'): missing.append("audio controls")
                if not template_compliance.get('has_notes_panel'): missing.append("notes panel")
                if not template_compliance.get('has_chatbot'): missing.append("chatbot")
                if not template_compliance.get('has_modules_array'): missing.append("modules array")
                
                template_section = f"""
**⚠️  Template Structure Issues:**
- Missing components: {', '.join(missing) if missing else 'None'}
- Modules count: {template_compliance.get('modules_count', 0)} (should be multiple modules)
**Deduct points for missing template components.**
"""
            else:
                template_section = "\n**✅ Template Structure: Verified - Template components present**\n"
        
        prompt = f"""# CRITICAL EVALUATION - Evidence-Based Assessment

**Original Task Requirements:**
{task}
{compliance_section}
{template_section}
**Autonomous Testing Results:**
- Total test steps: {exploration['steps_taken']}
- Completion status: {exploration['completion_reason']}
- Console errors found: {len(observation.console_errors)}

**Detailed Test Actions, Observations & Verification:**
"""
        
        for step in self.exploration_log:
            prompt += f"\n{step['step']}. {step['tool']}({step['args']})"
            if step.get('reasoning'):
                prompt += f"\n   💭 Agent: {step['reasoning'][:150]}"
            if step.get('verification'):
                v = step['verification']
                prompt += f"\n   🔍 Verify: DOM changed={v.get('dom_changed')}, Text changed={v.get('text_changed')}"
                if v.get('dialogs'):
                    prompt += f", ⚠️ Dialogs detected={len(v['dialogs'])}"
        
        prompt += f"""

**Console Errors:** {len(observation.console_errors)}
{f"Sample errors: {observation.console_errors[:2]}" if observation.console_errors else "None detected"}

**Dialogs Detected:** {sum(len(step.get('verification', {}).get('dialogs', [])) for step in self.exploration_log)}
(System dialogs indicate poor UX - should use in-page UI instead)

**EVALUATION RULES - Harsh but Fair:**

1. **Evidence-Based Scoring:**
   - Agent had vision (screenshots) + tools + verification signals
   - Trust the agent's observations: if it verified something works, credit it
   - If agent tried to interact but saw no change → mark as broken
   - If agent couldn't find/test a feature → deduct points

2. **Functionality Priority:**
   - Broken core features → heavy score penalty
   - Working core features → baseline score ≥60
   - Console errors → reduce robustness score
   - System dialogs → reduce UX score

3. **Visual Design Expectations:**
   - Modern, beautiful UI (not default browser styles)
   - Professional appearance, good spacing, colors
   - Smooth interactions (if verified working)

**Evaluation Rubric (MATCH THESE RANGES EXACTLY):**
"""
        
        for category, details in rubric.items():
            prompt += f"\n{category.upper()} (max {details['weight']} points):\n"
            for criterion in details['criteria']:
                prompt += f"  - {criterion}\n"
        
        # Calculate total to ensure it's 100
        total_weight = sum(details['weight'] for details in rubric.values())
        prompt += f"\nTotal: {total_weight} points\n"
        
        prompt += f"""

**Output Format (JSON):**
```json
{{
  "score": <0-100>,
  "passed": <true/false>,
  "category_scores": {{
    "functionality": <0-{rubric['functionality']['weight']}>,
    "visual_design": <0-{rubric['visual_design']['weight']}>,
    "ux": <0-{rubric['ux']['weight']}>,
    "accessibility": <0-{rubric['accessibility']['weight']}>,
    "responsiveness": <0-{rubric['responsiveness']['weight']}>,
    "robustness": <0-{rubric['robustness']['weight']}>
  }},
  "issues": [
    {{"severity": "critical|high|medium|low", "description": "Specific issue with evidence from testing"}}
  ],
  "suggestions": ["Concrete improvement 1", "Concrete improvement 2"]
}}
```

**Score must equal sum of category scores. Be honest based on evidence. Provide evaluation:**"""
        
        return prompt
    
    async def _inject_dialog_detection(self, mcp_client):
        """
        Inject JavaScript to detect and record system dialogs
        
        Wraps window.alert/confirm/prompt to record calls and prevent blocking
        """
        dialog_detection_js = """
        (function() {
            // Initialize dialog tracking
            window.__dialogCalls = window.__dialogCalls || [];
            
            // Wrap alert
            const originalAlert = window.alert;
            window.alert = function(message) {
                window.__dialogCalls.push({type: 'alert', message: String(message), timestamp: Date.now()});
                console.warn('[DIALOG DETECTED] alert:', message);
                // Don't actually show - return immediately
            };
            
            // Wrap confirm
            const originalConfirm = window.confirm;
            window.confirm = function(message) {
                window.__dialogCalls.push({type: 'confirm', message: String(message), timestamp: Date.now()});
                console.warn('[DIALOG DETECTED] confirm:', message);
                return false; // Auto-reject
            };
            
            // Wrap prompt
            const originalPrompt = window.prompt;
            window.prompt = function(message, defaultValue) {
                window.__dialogCalls.push({type: 'prompt', message: String(message), defaultValue: defaultValue, timestamp: Date.now()});
                console.warn('[DIALOG DETECTED] prompt:', message);
                return null; // Auto-cancel
            };
            
            // Disable beforeunload
            window.onbeforeunload = null;
            window.addEventListener('beforeunload', function(e) {
                window.__dialogCalls.push({type: 'beforeunload', timestamp: Date.now()});
                e.preventDefault();
                delete e['returnValue'];
            });
            
            return 'Dialog detection injected';
        })()
        """
        
        try:
            result = await mcp_client.evaluate(dialog_detection_js)
            logger.info(f"✓ Dialog detection injected: {result.get('result')}")
        except Exception as e:
            logger.warning(f"Failed to inject dialog detection: {e}")
    
    async def _get_dialog_calls(self, mcp_client) -> List[Dict[str, Any]]:
        """Get any detected dialog calls"""
        try:
            dialog_js = "window.__dialogCalls || []"
            result = await mcp_client.evaluate(dialog_js)
            dialogs = result.get("result", [])
            return dialogs if isinstance(dialogs, list) else []
        except:
            return []
    
    async def _discover_interactive_targets(self, mcp_client) -> List[Dict[str, Any]]:
        """
        Discover interactive elements with stable selectors
        
        Returns ranked list of actionable targets with:
        - Stable selector (prefer #id, fallback to other strategies)
        - Element role/tag
        - Accessible name/text
        - Visibility info
        """
        discover_js = """
        (function() {
            function computeSelector(el) {
                // Prefer ID
                if (el.id) return '#' + el.id;
                
                // Try data-testid
                if (el.dataset.testid) return '[data-testid="' + el.dataset.testid + '"]';
                
                // Try aria-label
                if (el.getAttribute('aria-label')) {
                    const label = el.getAttribute('aria-label').replace(/"/g, '\\\\"');
                    return el.tagName.toLowerCase() + '[aria-label="' + label + '"]';
                }
                
                // Try name attribute
                if (el.name) {
                    return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
                }
                
                // Fallback: tag + class (first class only)
                if (el.className && typeof el.className === 'string') {
                    const firstClass = el.className.split(' ')[0];
                    if (firstClass) return el.tagName.toLowerCase() + '.' + firstClass;
                }
                
                // Last resort: tag only (not great but better than nothing)
                return el.tagName.toLowerCase();
            }
            
            function isVisible(el) {
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       style.opacity !== '0' &&
                       el.offsetParent !== null;
            }
            
            function getText(el) {
                return (el.textContent || el.value || el.getAttribute('aria-label') || el.placeholder || '').trim();
            }
            
            // Find interactive elements
            const selectors = [
                'button', 'a[href]', 'input', 'select', 'textarea', 
                '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="radio"]',
                '[tabindex]', 'summary', 'details'
            ];
            
            const elements = [];
            document.querySelectorAll(selectors.join(', ')).forEach((el, idx) => {
                if (idx >= 50) return; // Limit to 50 elements
                
                const visible = isVisible(el);
                if (!visible) return; // Skip invisible elements
                
                elements.push({
                    selector: computeSelector(el),
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    text: getText(el).slice(0, 100),
                    type: el.type || null,
                    visible: visible
                });
            });
            
            return elements;
        })()
        """
        
        try:
            result = await mcp_client.evaluate(discover_js)
            targets = result.get("result", [])
            return targets if isinstance(targets, list) else []
        except Exception as e:
            logger.error(f"Failed to discover interactive targets: {e}")
            return []
    
    async def _compute_dom_signature(self, mcp_client) -> str:
        """
        Compute a DOM change signature for verification
        
        Uses: text content hash + element counts + URL
        """
        signature_js = """
        (function() {
            const text = document.body.innerText.slice(0, 1500);
            const buttonCount = document.querySelectorAll('button').length;
            const inputCount = document.querySelectorAll('input').length;
            const linkCount = document.querySelectorAll('a').length;
            const url = window.location.href;
            
            return JSON.stringify({
                text: text,
                buttons: buttonCount,
                inputs: inputCount,
                links: linkCount,
                url: url
            });
        })()
        """
        
        try:
            result = await mcp_client.evaluate(signature_js)
            sig_json = result.get("result", "{}")
            # Hash it
            sig_hash = hashlib.md5(sig_json.encode()).hexdigest()
            return sig_hash
        except:
            return ""
    
    def _compute_verification(self, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute verification signals comparing before/after states
        
        Returns:
            Dict with dom_changed, text_changed, new_console_errors, dialogs
        """
        before_sig = before_state.get("dom_signature", "")
        after_sig = after_state.get("dom_signature", "")
        dom_changed = before_sig != after_sig if (before_sig and after_sig) else False
        
        before_text = before_state.get("text_snippet", "")
        after_text = after_state.get("text_snippet", "")
        text_changed = before_text != after_text
        
        before_errors = set(str(e) for e in before_state.get("console_errors", []))
        after_errors = set(str(e) for e in after_state.get("console_errors", []))
        new_errors = list(after_errors - before_errors)
        
        after_dialogs = after_state.get("dialogs", [])
        before_dialogs = before_state.get("dialogs", [])
        new_dialogs = after_dialogs[len(before_dialogs):] if len(after_dialogs) > len(before_dialogs) else []
        
        return {
            "dom_changed": dom_changed,
            "text_changed": text_changed,
            "new_console_errors": new_errors,
            "dialogs": new_dialogs,
            "before_sig": before_sig[:16],
            "after_sig": after_sig[:16]
        }
    
    def _compact_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create compact version of state for logging"""
        return {
            "screenshot": state.get("screenshot_path"),
            "text_length": len(state.get("visible_text", "")),
            "targets_count": len(state.get("interactive_targets", [])),
            "console_errors": len(state.get("console_errors", [])),
            "dom_sig": state.get("dom_signature", "")[:16],
            "url": state.get("current_url", "")
        }
    
    def _parse_evaluation_response(self, response_text: str) -> EvaluationResult:
        """
        Parse Gemini's evaluation response into EvaluationResult
        
        Properly parses issues into EvaluationIssue objects
        """
        
        try:
            # Extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else response_text
            
            data = json.loads(json_str)
            
            # Parse issues into EvaluationIssue objects
            issues = []
            for issue_dict in data.get("issues", []):
                if isinstance(issue_dict, dict):
                    issues.append(EvaluationIssue(
                        category=issue_dict.get("category", "general"),
                        severity=issue_dict.get("severity", "medium"),
                        description=issue_dict.get("description", ""),
                        repro_steps=issue_dict.get("repro_steps", []),
                        screenshot_reference=issue_dict.get("screenshot_reference")
                    ))
                elif isinstance(issue_dict, str):
                    # Fallback: plain string issue
                    issues.append(EvaluationIssue(
                        category="general",
                        severity="medium",
                        description=issue_dict,
                        repro_steps=[]
                    ))
            
            return EvaluationResult(
                score=data.get("score", 0),
                passed=data.get("passed", False),
                issues=issues,
                fix_suggestions=data.get("suggestions", []),
                feedback=response_text,
                category_scores=data.get("category_scores", {}),
                observations=BrowserObservation()
            )
        
        except Exception as e:
            logger.error(f"Failed to parse evaluation response: {e}")
            logger.error(f"Response: {response_text[:500]}")
            
            # Return default result
            return EvaluationResult(
                score=50,
                passed=False,
                issues=[],
                fix_suggestions=[],
                feedback=response_text,
                category_scores={},
                observations=BrowserObservation()
            )
