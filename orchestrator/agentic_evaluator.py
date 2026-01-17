"""
Agentic Evaluator - Gemini Controls Browser Directly

Instead of scripted tests, Gemini autonomously explores the page using MCP browser tools.
Implements an observe→act loop where Gemini sees screenshots and chooses actions.
"""

import os
import logging
import json
import asyncio
from dataclasses import asdict
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

from .evaluator import (
    GeminiEvaluator, 
    EvaluationResult, 
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
    1. Load page
    2. Observe→Act loop: Get state (with screenshot) → Gemini picks action → Execute → Repeat
    3. After N steps or "finish_exploration", run final vision evaluation
    """
    
    def __init__(self, max_exploration_steps: int = 15):
        super().__init__()
        self.max_exploration_steps = max_exploration_steps
        self.exploration_log = []
        
        # Configure Gemini with function calling
        self.agent_model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
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
        
        # Phase 1: Navigate to page
        logger.info("\n📍 Phase 1: Navigate to page")
        await mcp_client.navigate(url)
        await asyncio.sleep(2)  # Let page load
        
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
        Run observe→act loop where Gemini chooses actions
        
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
            
            # Observe: Get current browser state with screenshot
            logger.info("📸 Observing browser state...")
            state = await self._get_browser_state(mcp_client, artifacts_dir, step)
            
            # Build observation message for Gemini
            observation_msg = self._format_observation(state, step)
            
            # Act: Let Gemini choose next action
            logger.info("🤔 Gemini choosing next action...")
            
            try:
                # Send observation + request action
                if step == 0:
                    # First step: include system prompt
                    full_msg = f"{agent_prompt}\n\n{observation_msg}"
                else:
                    full_msg = observation_msg
                
                response = chat.send_message(full_msg)
                
                # Check if Gemini called a tool
                if response.candidates[0].content.parts:
                    part = response.candidates[0].content.parts[0]
                    
                    if hasattr(part, 'function_call'):
                        func_call = part.function_call
                        
                        # Handle None args defensively
                        args_dict = dict(func_call.args) if func_call.args else {}
                        
                        logger.info(f"🔧 Tool call: {func_call.name}")
                        logger.info(f"   Args: {args_dict}")
                        
                        # Log the step
                        step_log = {
                            "step": step + 1,
                            "tool": func_call.name,
                            "args": args_dict,
                            "screenshot": state.get("screenshot_path"),
                            "reasoning": response.candidates[0].content.parts[0].text if len(response.candidates[0].content.parts) > 1 else "No reasoning provided"
                        }
                        self.exploration_log.append(step_log)
                        
                        # Execute the tool
                        if func_call.name == "finish_exploration":
                            logger.info(f"✅ Gemini finished exploration")
                            logger.info(f"   Summary: {args_dict.get('summary', 'N/A')}")
                            finished = True
                            final_observation = state
                            break
                        else:
                            # Execute browser action
                            tool_result = await self._execute_tool(
                                func_call.name,
                                args_dict,
                                mcp_client
                            )
                            
                            logger.info(f"   Result: {tool_result.get('success', False)}")
                            
                            # Send tool result back to Gemini
                            chat.send_message(
                                genai.protos.Content(parts=[
                                    genai.protos.Part(function_response=genai.protos.FunctionResponse(
                                        name=func_call.name,
                                        response=tool_result
                                    ))
                                ])
                            )
                    else:
                        logger.warning("⚠️  No function call in response")
                        if hasattr(part, 'text'):
                            logger.info(f"   Text: {part.text[:200]}")
                
            except Exception as e:
                logger.error(f"❌ Error in exploration step: {e}")
                import traceback
                logger.error(traceback.format_exc())
                break
        
        if not finished:
            logger.info(f"\n⏱️  Reached max steps ({self.max_exploration_steps})")
            final_observation = state
        
        return {
            "steps_taken": steps_taken,
            "completion_reason": "agent_finished" if finished else "max_steps_reached",
            "final_observation": final_observation
        }
    
    def _build_agent_prompt(self, task: str) -> str:
        """Build system prompt for agentic exploration"""
        
        return f"""You are an autonomous browser testing agent. Your job is to THOROUGHLY test a web page and VERIFY everything works.

**Task Description:**
{task}

**Your Mission - BE CRITICAL:**
1. Test EVERY interactive element listed in the task
2. After EACH click/interaction, check if something changed (new content, animations, state updates)
3. If something doesn't work or shows errors, note it as a FAILURE
4. Scroll through the ENTIRE page to see all content
5. Test edge cases (empty inputs, multiple clicks, etc.)
6. Only call finish_exploration when you've tested EVERYTHING

**Available Tools:**
- browser_click: Click elements (use CSS selectors like 'button', '#id', '.class')
- browser_type: Type into input fields
- browser_scroll: Scroll up/down to see ALL content
- browser_evaluate: Check JavaScript state, get values, verify calculations
- finish_exploration: Signal done testing (include DETAILED summary of what worked/failed)

**Critical Testing Strategy:**
1. SCROLL FIRST - See what's on the page
2. TEST EACH FEATURE from the task requirements
3. VERIFY the result after each interaction:
   - Did the button respond?
   - Did content appear/change?
   - Are there visual bugs (blank areas, missing content)?
   - Any console errors?
4. Use browser_evaluate to check:
   - Canvas drawing (ctx methods called?)
   - Form values updated?
   - Calculations correct?
5. Only finish when you've tested EVERYTHING listed in task

**IMPORTANT - Be Harsh:**
- Blank/dark canvases = FAILURE
- Buttons that don't respond = FAILURE  
- Missing interactive features = FAILURE
- Console errors = FAILURE
- Test EVERY requirement from the task description
- Your summary must list what WORKS and what FAILS

Begin thorough testing now. Be critical!"""
    
    def _format_observation(self, state: Dict[str, Any], step: int) -> str:
        """Format browser state as observation message for Gemini"""
        
        obs = f"**Step {step + 1} Observation:**\n\n"
        
        if state.get("screenshot_path"):
            obs += f"Screenshot captured: {state['screenshot_path']}\n"
        
        if state.get("visible_text"):
            obs += f"\n**Visible Text (first 500 chars):**\n{state['visible_text'][:500]}\n"
        
        if state.get("interactive_elements"):
            obs += f"\n**Interactive Elements Found:**\n"
            for elem in state['interactive_elements'][:10]:  # First 10
                obs += f"  - {elem}\n"
        
        if state.get("console_errors"):
            obs += f"\n**Console Errors:** {len(state['console_errors'])}\n"
        
        obs += "\n**What would you like to do next?** (Call a tool to continue exploration)"
        
        return obs
    
    async def _get_browser_state(
        self,
        mcp_client,
        artifacts_dir: Path,
        step: int
    ) -> Dict[str, Any]:
        """Get comprehensive browser state"""
        
        state = {}
        
        # Take screenshot
        screenshot_path = artifacts_dir / f"step_{step + 1}.png"
        await mcp_client.screenshot(str(screenshot_path))
        state["screenshot_path"] = str(screenshot_path)
        
        # Get page content
        try:
            content = await mcp_client.get_content()
            state["visible_text"] = content.get("text", "")
        except:
            state["visible_text"] = ""
        
        # Get interactive elements
        try:
            elements_js = """
            Array.from(document.querySelectorAll('button, a, input, select, textarea')).map(el => {
                return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : '');
            }).slice(0, 20);
            """
            result = await mcp_client.evaluate(elements_js)
            state["interactive_elements"] = result.get("result", [])
        except:
            state["interactive_elements"] = []
        
        # Get console errors
        try:
            messages = await mcp_client.get_console_messages()
            state["console_errors"] = [m for m in messages if m.get("level") == "error"]
        except:
            state["console_errors"] = []
        
        return state
    
    async def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        mcp_client
    ) -> Dict[str, Any]:
        """Execute a browser tool and return result"""
        
        try:
            if tool_name == "browser_click":
                await mcp_client.click(args["selector"])
                await asyncio.sleep(1)  # Wait after click
                return {"success": True, "message": f"Clicked {args['selector']}"}
            
            elif tool_name == "browser_type":
                await mcp_client.type_text(args["selector"], args["text"])
                return {"success": True, "message": f"Typed into {args['selector']}"}
            
            elif tool_name == "browser_scroll":
                direction = args["direction"]
                amount = args.get("amount", 500)
                await mcp_client.scroll(direction, amount)
                return {"success": True, "message": f"Scrolled {direction} {amount}px"}
            
            elif tool_name == "browser_evaluate":
                result = await mcp_client.evaluate(args["expression"])
                return {"success": True, "result": result.get("result")}
            
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
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
        """Build prompt for final vision evaluation"""
        
        prompt = f"""# CRITICAL EVALUATION - Be Harsh on Broken Functionality

**Original Task Requirements:**
{task}

**Autonomous Testing Results:**
- Total test steps: {exploration['steps_taken']}
- Completion status: {exploration['completion_reason']}
- Console errors found: {len(observation.console_errors)}

**Detailed Test Actions & Observations:**
"""
        
        for step in self.exploration_log:
            prompt += f"\n{step['step']}. {step['tool']}({step['args']})"
            if step.get('reasoning'):
                prompt += f"\n   Agent's observation: {step['reasoning'][:200]}"
        
        prompt += f"""

**Console Errors Detected:** {len(observation.console_errors)}
{f"Errors: {observation.console_errors[:3]}" if observation.console_errors else "None"}

**CRITICAL EVALUATION RULES:**

1. **FUNCTIONALITY IS KING (40% of score)**
   - If interactive features don't work → score ≤ 40
   - If buttons don't respond → score ≤ 30
   - If main features from task are broken/missing → FAIL
   - Blank canvases, dark displays, no interaction = BROKEN

2. **Compare Task vs Reality:**
   - List each requirement from task
   - Did testing verify it works? YES/NO
   - If NO → deduct heavily from functionality score

3. **Evidence-Based Scoring:**
   - Use exploration log as evidence
   - If agent couldn't verify a feature → assume BROKEN
   - If agent found errors → mark as FAILURE
   - If console errors → robustness = 0

4. **No Mercy for Broken Pages:**
   - Pretty but broken = score < 50
   - Working but ugly = score 60-80
   - Working AND pretty = score 80-100

**Evaluation Rubric:**
"""
        
        for category, details in rubric.items():
            prompt += f"\n{category.upper()} ({details['weight']} points):\n"
            for criterion in details['criteria']:
                prompt += f"  - {criterion}\n"
        
        prompt += """

**Output Format (JSON):**
```json
{
  "score": <0-100>,
  "passed": <true/false>,
  "category_scores": {
    "functionality": <0-25>,
    "visual_design": <0-35>,
    "ux": <0-15>,
    "accessibility": <0-20>,
    "responsiveness": <0-20>,
    "robustness": <0-5>
  },
  "issues": [
    {"severity": "critical", "description": "Specific feature X doesn't work - agent clicked but no response"}
  ],
  "suggestions": ["Fix feature X", "Add Y"]
}
```

**Be brutally honest. If features don't work, give a LOW score. Provide your evaluation:**"""
        
        return prompt
    
    def _parse_evaluation_response(self, response_text: str) -> EvaluationResult:
        """Parse Gemini's evaluation response into EvaluationResult"""
        
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
            
            return EvaluationResult(
                score=data.get("score", 0),
                passed=data.get("passed", False),
                issues=[],  # Parse from data["issues"]
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
