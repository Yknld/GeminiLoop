"""
Agentic Evaluator - Gemini Controls Browser Directly

Instead of scripted tests, Gemini autonomously explores the page using MCP browser tools.
Implements an observe→act loop where Gemini sees screenshots and chooses actions.
"""

import os
import logging
import json
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
        await mcp_client.wait(2000)  # Let page load
        
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
            "final_evaluation": final_eval.to_dict()
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
                        
                        logger.info(f"🔧 Tool call: {func_call.name}")
                        logger.info(f"   Args: {dict(func_call.args)}")
                        
                        # Log the step
                        step_log = {
                            "step": step + 1,
                            "tool": func_call.name,
                            "args": dict(func_call.args),
                            "screenshot": state.get("screenshot_path"),
                            "reasoning": response.candidates[0].content.parts[0].text if len(response.candidates[0].content.parts) > 1 else "No reasoning provided"
                        }
                        self.exploration_log.append(step_log)
                        
                        # Execute the tool
                        if func_call.name == "finish_exploration":
                            logger.info(f"✅ Gemini finished exploration")
                            logger.info(f"   Summary: {func_call.args.get('summary', 'N/A')}")
                            finished = True
                            final_observation = state
                            break
                        else:
                            # Execute browser action
                            tool_result = await self._execute_tool(
                                func_call.name,
                                dict(func_call.args),
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
        
        return f"""You are an autonomous browser testing agent. Your job is to explore and test a web page.

**Task Description:**
{task}

**Your Mission:**
1. Explore the page systematically
2. Test all interactive elements (buttons, forms, links, etc.)
3. Verify core functionality works as described in the task
4. Capture observations about UX, design, and any issues
5. When satisfied, call finish_exploration with a summary

**Available Tools:**
- browser_get_state: See current page state (screenshot, DOM, console)
- browser_click: Click elements (use CSS selectors)
- browser_type: Type into input fields
- browser_scroll: Scroll up/down
- browser_evaluate: Execute JavaScript
- finish_exploration: Signal you're done testing

**Strategy:**
- Start with browser_get_state to see what's on the page
- Click buttons/links to test interactions
- Try filling forms if present
- Check different sections by scrolling
- When you've tested core features, call finish_exploration

**Important:**
- Use specific CSS selectors (e.g., 'button:first-of-type', '#submit', '.card')
- Test one thing at a time
- Be thorough but efficient (max {self.max_exploration_steps} steps)
- Focus on verifying the task requirements are met

Begin exploration now."""
    
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
            if tool_name == "browser_navigate":
                await mcp_client.navigate(args["url"])
                return {"success": True, "message": f"Navigated to {args['url']}"}
            
            elif tool_name == "browser_get_state":
                # State already captured in main loop
                return {"success": True, "message": "State captured"}
            
            elif tool_name == "browser_click":
                await mcp_client.click(args["selector"])
                await mcp_client.wait(1000)  # Wait after click
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
        
        # Call Gemini for final scoring
        model = genai.GenerativeModel(
            model_name=os.getenv("EVALUATOR_MODEL", "gemini-3-flash-preview")
        )
        
        response = model.generate_content(prompt)
        
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
        
        prompt = f"""# Final Evaluation

**Original Task:**
{task}

**Autonomous Exploration Summary:**
- Steps taken: {exploration['steps_taken']}
- Completion: {exploration['completion_reason']}
- Interactions tested: {len(self.exploration_log)}

**Exploration Actions Performed:**
"""
        
        for step in self.exploration_log[:10]:  # Show first 10 steps
            prompt += f"\n{step['step']}. {step['tool']}({step['args']})"
        
        if len(self.exploration_log) > 10:
            prompt += f"\n... and {len(self.exploration_log) - 10} more steps"
        
        prompt += f"""

**Console Errors:** {len(observation.console_errors)}

**Your Task:**
Evaluate the page based on the rubric below and the autonomous exploration results.

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
    "functionality": <0-weight>,
    "visual_design": <0-weight>,
    ...
  },
  "issues": [
    {"severity": "high/medium/low", "description": "..."}
  ],
  "suggestions": ["...", "..."]
}
```

Provide your evaluation now."""
        
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
                suggestions=data.get("suggestions", []),
                feedback=response_text,
                category_scores=data.get("category_scores", {})
            )
        
        except Exception as e:
            logger.error(f"Failed to parse evaluation response: {e}")
            logger.error(f"Response: {response_text[:500]}")
            
            # Return default result
            return EvaluationResult(
                score=50,
                passed=False,
                issues=[],
                suggestions=[],
                feedback=response_text
            )
