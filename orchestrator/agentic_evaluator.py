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
    
    def __init__(self, max_exploration_steps: int = 15):
        super().__init__()
        self.max_exploration_steps = max_exploration_steps
        self.exploration_log = []
        self.step_artifacts = []  # Per-step artifact metadata
        
        # Configure Gemini with function calling
        self.agent_model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
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
        
        # Phase 3: Final vision evaluation
        logger.info("\n👁️  Phase 3: Final Vision Evaluation")
        final_eval = await self._run_vision_evaluation(
            task,
            exploration_result["final_observation"],
            rubric,
            exploration_result
        )
        
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
                
                # Parse function calls (robust parsing with multiple parts support)
                reasoning_text = ""
                function_calls = []
                
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                reasoning_text += part.text
                            if hasattr(part, 'function_call') and part.function_call:
                                function_calls.append(part.function_call)
                
                logger.info(f"   💭 Reasoning: {reasoning_text[:150]}")
                
                if function_calls:
                    # Execute first function call (log if multiple)
                    if len(function_calls) > 1:
                        logger.warning(f"⚠️  Multiple function calls detected ({len(function_calls)}), executing first only")
                    
                    func_call = function_calls[0]
                    args_dict = dict(func_call.args) if func_call.args else {}
                    
                    logger.info(f"🔧 Tool call: {func_call.name}")
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
                    result_with_verification = {
                        **tool_result,
                        "verification": {
                            "dom_changed": verification["dom_changed"],
                            "visible_text_changed": verification["text_changed"],
                            "dialogs_detected": len(verification["dialogs"]) > 0,
                            "console_errors_new": len(verification["new_console_errors"])
                        }
                    }
                    
                    chat.send_message(
                        genai.protos.Content(parts=[
                            genai.protos.Part(function_response=genai.protos.FunctionResponse(
                                name=func_call.name,
                                response=result_with_verification
                            ))
                        ])
                    )
                else:
                    logger.warning("⚠️  No function call in response")
                    logger.info(f"   Reasoning text: {reasoning_text[:300]}")
                
            except Exception as e:
                logger.error(f"❌ Error in exploration step: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break
        
        if not finished:
            logger.info(f"\n⏱️  Reached max steps ({self.max_exploration_steps})")
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
        
        # Get page visible text
        try:
            text_js = "document.body.innerText"
            result = await mcp_client.evaluate(text_js)
            visible_text = result.get("result", "")
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
                # Use MCP client's click if available, otherwise fallback to evaluate
                try:
                    await mcp_client.call_tool("browser_click", {"selector": selector})
                except:
                    # Fallback: click via JS
                    click_js = f"document.querySelector({json.dumps(selector)})?.click()"
                    await mcp_client.evaluate(click_js)
                return {"success": True, "message": f"Clicked {selector}"}
            
            elif tool_name == "browser_type":
                selector = args["selector"]
                text = args["text"]
                try:
                    await mcp_client.call_tool("browser_type", {"selector": selector, "text": text})
                except:
                    # Fallback: type via JS
                    type_js = f"""
                    const el = document.querySelector({json.dumps(selector)});
                    if (el) {{ el.value = {json.dumps(text)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); }}
                    """
                    await mcp_client.evaluate(type_js)
                return {"success": True, "message": f"Typed '{text}' into {selector}"}
            
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
        exploration_result: Dict[str, Any]
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
        prompt = self._build_vision_prompt(task, observation, rubric, exploration_result)
        
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
    
    def _build_vision_prompt(
        self,
        task: str,
        observation: BrowserObservation,
        rubric: Dict[str, Any],
        exploration: Dict[str, Any]
    ) -> str:
        """Build prompt for final vision evaluation with correct rubric weights"""
        
        prompt = f"""# CRITICAL EVALUATION - Evidence-Based Assessment

**Original Task Requirements:**
{task}

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
