"""
Gemini-Controlled Browser QA Evaluator

Comprehensive evaluation system that:
1. Uses MCP browser tools to interact with the page
2. Tests functionality, UX, accessibility, responsiveness
3. Collects multiple observations (screenshots, logs, DOM)
4. Uses Gemini to analyze and provide structured feedback
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

try:
    import google.generativeai as genai
    import PIL.Image
except ImportError:
    raise ImportError("Install google-generativeai: pip install google-generativeai")

logger = logging.getLogger(__name__)

# Model version constants
EVALUATOR_MODEL_VERSION = "gemini-2.5-flash-image"
RUBRIC_VERSION = "1.0"

# Rubric Schema
EVALUATION_RUBRIC = {
    "functionality": {
        "weight": 25,
        "description": "Core features work as expected",
        "criteria": [
            "All interactive elements are functional",
            "Buttons, links, and forms work correctly",
            "User workflows complete successfully",
            "No JavaScript errors in console"
        ]
    },
    "visual_design": {
        "weight": 25,
        "description": "Visual design is modern, beautiful, and professional",
        "criteria": [
            "BEAUTIFUL, modern aesthetic (not basic HTML)",
            "Professional color scheme and typography",
            "Smooth animations and transitions",
            "Proper spacing, padding, and visual rhythm",
            "High-quality UI that looks like a real product",
            "No ugly default browser styles",
            "Polished, production-ready appearance"
        ]
    },
    "ux": {
        "weight": 15,
        "description": "User experience is intuitive and pleasant",
        "criteria": [
            "Clear visual hierarchy",
            "Intuitive navigation and flow",
            "Appropriate feedback for user actions"
        ]
    },
    "accessibility": {
        "weight": 15,
        "description": "Accessible to all users",
        "criteria": [
            "Semantic HTML elements",
            "Proper ARIA labels where needed",
            "Keyboard navigation works",
            "Good color contrast"
        ]
    },
    "responsiveness": {
        "weight": 15,
        "description": "Works well on different screen sizes",
        "criteria": [
            "Mobile layout (375px) is usable",
            "Desktop layout is optimal",
            "No horizontal scrolling on mobile",
            "Touch targets are adequate"
        ]
    },
    "robustness": {
        "weight": 5,
        "description": "Handles edge cases and errors gracefully",
        "criteria": [
            "No console errors",
            "Graceful error handling",
            "No broken functionality",
            "Stable under interaction"
        ]
    }
}


@dataclass
class BrowserObservation:
    """Observations collected from browser testing"""
    desktop_screenshot: Optional[str] = None
    mobile_screenshot: Optional[str] = None
    console_logs: List[Dict[str, str]] = None
    console_errors: List[Dict[str, str]] = None
    dom_snapshot: Optional[Dict[str, Any]] = None
    interactions_performed: List[str] = None
    interaction_results: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.console_logs is None:
            self.console_logs = []
        if self.console_errors is None:
            self.console_errors = []
        if self.interactions_performed is None:
            self.interactions_performed = []
        if self.interaction_results is None:
            self.interaction_results = {}


@dataclass
class EvaluationIssue:
    """Individual issue found during evaluation"""
    category: str
    severity: str  # critical, high, medium, low
    description: str
    repro_steps: List[str]
    screenshot_reference: Optional[str] = None


@dataclass
class EvaluationResult:
    """Complete evaluation result"""
    score: int  # 0-100
    passed: bool
    category_scores: Dict[str, int]
    issues: List[EvaluationIssue]
    fix_suggestions: List[str]
    observations: BrowserObservation
    feedback: str


class GeminiEvaluator:
    """
    Gemini-powered browser QA evaluator
    
    Performs comprehensive testing including:
    - Interactive browser testing
    - Multi-viewport screenshots
    - Console log analysis
    - Structured evaluation with rubric
    """
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        # Use Gemini 3 Flash for evaluation
        self.model = genai.GenerativeModel(EVALUATOR_MODEL_VERSION)
        
        logger.info("Gemini Evaluator initialized")
    
    async def evaluate(
        self,
        url: str,
        mcp_client,
        task: str,
        screenshots_dir: Path,
        rubric: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Comprehensive evaluation using Gemini-controlled browser QA
        
        Args:
            url: URL to evaluate (http:// - file:// URLs are NOT supported)
            mcp_client: MCP client for browser automation
            task: Original task description
            screenshots_dir: Directory to save screenshots
            rubric: Optional custom rubric (defaults to EVALUATION_RUBRIC)
        
        Returns:
            EvaluationResult with score, issues, and suggestions
        
        Note:
            Only HTTP URLs are supported. file:// URLs will fail in most
            deployment contexts (RunPod, Docker, etc.)
        """
        
        rubric = rubric or EVALUATION_RUBRIC
        screenshots_dir = Path(screenshots_dir)
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🧠 Starting Gemini-controlled browser QA")
        logger.info(f"   URL: {url}")
        
        # Validate URL protocol
        if url.startswith("file://"):
            logger.warning("⚠️  file:// URL detected - this may fail in RunPod/Docker")
            logger.warning("   Consider using HTTP preview server instead")
        elif not url.startswith("http://") and not url.startswith("https://"):
            logger.error(f"❌ Invalid URL protocol: {url}")
            logger.error("   Expected http:// or https:// URL")
        
        # Collect browser observations
        observations = await self._collect_observations(
            url=url,
            mcp_client=mcp_client,
            screenshots_dir=screenshots_dir
        )
        
        # Analyze with Gemini
        evaluation = await self._analyze_with_gemini(
            task=task,
            observations=observations,
            rubric=rubric
        )
        
        return evaluation
    
    async def _collect_observations(
        self,
        url: str,
        mcp_client,
        screenshots_dir: Path
    ) -> BrowserObservation:
        """
        Collect observations from browser testing
        
        Performs interactive testing and captures evidence
        """
        
        observation = BrowserObservation()
        
        logger.info("📊 Collecting browser observations...")
        
        # Navigate to page
        logger.info(f"   Navigating to: {url}")
        try:
            await mcp_client.navigate(url)
            observation.interactions_performed.append("navigate")
            observation.interaction_results["navigate"] = True
        except Exception as e:
            logger.error(f"   Navigation failed: {e}")
            observation.interaction_results["navigate"] = False
            return observation
        
        # Wait a moment for page to stabilize
        try:
            # Try browser_wait first, fallback to browser_wait_for if needed
            try:
                await mcp_client.call_tool("browser_wait", {"duration": 1000})
            except:
                await mcp_client.call_tool("browser_wait_for", {"time": 1.0})
        except:
            pass
        
        # Desktop screenshot
        logger.info("   Taking desktop screenshot (1440x900)...")
        try:
            desktop_path = screenshots_dir / "desktop.png"
            # Convert Path to string for screenshot call
            await mcp_client.screenshot(str(desktop_path))
            observation.desktop_screenshot = str(desktop_path)
            observation.interactions_performed.append("screenshot_desktop")
        except Exception as e:
            logger.error(f"   Desktop screenshot failed: {e}")
        
        # Get DOM snapshot
        logger.info("   Getting DOM snapshot...")
        try:
            # Try snapshot() method first, fallback to call_tool
            if hasattr(mcp_client, 'snapshot'):
                snapshot = await mcp_client.snapshot()
            else:
                snapshot = await mcp_client.call_tool("browser_snapshot", {})
            observation.dom_snapshot = snapshot
            observation.interactions_performed.append("snapshot")
        except Exception as e:
            logger.error(f"   Snapshot failed: {e}")
        
        # Interactive testing - try common interactions
        await self._test_interactions(mcp_client, observation)
        
        # Mobile responsive test
        logger.info("   Testing mobile responsiveness (375px)...")
        try:
            # Use set_viewport method (replaces window.resizeTo which doesn't work in headless)
            if hasattr(mcp_client, 'set_viewport'):
                await mcp_client.set_viewport(375, 667)
            else:
                # Fallback to call_tool for compatibility
                await mcp_client.call_tool("set_viewport", {"width": 375, "height": 667})
            
            # Wait for resize
            try:
                await mcp_client.call_tool("browser_wait", {"duration": 500})
            except:
                try:
                    await mcp_client.call_tool("browser_wait_for", {"time": 0.5})
                except:
                    pass
            
            # Mobile screenshot
            mobile_path = screenshots_dir / "mobile.png"
            # Convert Path to string for screenshot call
            await mcp_client.screenshot(str(mobile_path))
            observation.mobile_screenshot = str(mobile_path)
            observation.interactions_performed.append("screenshot_mobile")
        except Exception as e:
            logger.error(f"   Mobile test failed: {e}")
        
        # Get console logs
        logger.info("   Collecting console logs...")
        try:
            # Try get_console() method first, fallback to call_tool
            if hasattr(mcp_client, 'get_console'):
                console_messages = await mcp_client.get_console()
            else:
                result = await mcp_client.call_tool("browser_console_messages", {})
                console_messages = result.get("messages", [])
            
            observation.console_logs = console_messages
            # Check both 'type' and 'level' fields for errors
            observation.console_errors = [
                msg for msg in console_messages
                if msg.get("type") == "error" or msg.get("level") == "error"
            ]
            observation.interactions_performed.append("console_logs")
        except Exception as e:
            logger.error(f"   Console log collection failed: {e}")
        
        logger.info(f"   ✅ Observations collected:")
        logger.info(f"      Interactions: {len(observation.interactions_performed)}")
        logger.info(f"      Screenshots: {2 if observation.mobile_screenshot else 1}")
        logger.info(f"      Console errors: {len(observation.console_errors)}")
        
        return observation
    
    async def _test_interactions(self, mcp_client, observation: BrowserObservation):
        """
        Test common interactive elements
        
        Tries to interact with standard elements, fails gracefully
        """
        
        # Generic selectors that work for any page
        test_cases = [
            ("button_first", 'button:first-of-type'),
            ("button_second", 'button:nth-of-type(2)'),
            ("button_primary", 'button[class*="primary"], button[class*="btn"]'),
            ("link_first", 'a:first-of-type'),
            ("input_first", 'input:first-of-type'),
        ]
        
        for test_name, selector in test_cases:
            try:
                logger.info(f"   Testing: {test_name} ({selector})")
                
                # Check if element exists
                exists_result = await mcp_client.call_tool("browser_evaluate", {
                    "expression": f"!!document.querySelector('{selector}')"
                })
                
                if exists_result and exists_result.get("result"):
                    # Element exists, try to interact
                    if "button" in test_name or "cta" in test_name:
                        # Try clicking
                        await mcp_client.call_tool("browser_click", {"selector": selector})
                        observation.interactions_performed.append(f"click_{test_name}")
                        observation.interaction_results[f"click_{test_name}"] = True
                        
                        # Wait after click
                        try:
                            await mcp_client.call_tool("browser_wait", {"duration": 500})
                        except:
                            try:
                                await mcp_client.call_tool("browser_wait_for", {"time": 0.5})
                            except:
                                pass
                        
                        logger.info(f"      ✅ Clicked {test_name}")
                    
                    elif "input" in test_name:
                        # Try filling - use browser_type or browser_fill
                        try:
                            await mcp_client.call_tool("browser_type", {
                                "selector": selector,
                                "text": "test input"
                            })
                        except:
                            # Fallback to browser_fill if browser_type doesn't exist
                            try:
                                await mcp_client.call_tool("browser_fill", {
                                    "selector": selector,
                                    "value": "test input"
                                })
                            except:
                                raise
                        observation.interactions_performed.append(f"fill_{test_name}")
                        observation.interaction_results[f"fill_{test_name}"] = True
                        
                        logger.info(f"      ✅ Filled {test_name}")
                else:
                    logger.info(f"      ℹ️  {test_name} not found")
                    observation.interaction_results[test_name] = False
                    
            except Exception as e:
                logger.info(f"      ⚠️  {test_name} interaction failed: {e}")
                observation.interaction_results[test_name] = False
    
    async def _analyze_with_gemini(
        self,
        task: str,
        observations: BrowserObservation,
        rubric: Dict[str, Any]
    ) -> EvaluationResult:
        """
        Analyze observations with Gemini to generate evaluation
        """
        
        logger.info("🤖 Analyzing with Gemini...")
        
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(task, observations, rubric)
        
        # Prepare images for Gemini - use PIL.Image for better reliability
        images = []
        if observations.desktop_screenshot and Path(observations.desktop_screenshot).exists():
            try:
                img = PIL.Image.open(observations.desktop_screenshot)
                images.append(img)
            except Exception as e:
                logger.warning(f"Failed to load desktop screenshot: {e}")
        if observations.mobile_screenshot and Path(observations.mobile_screenshot).exists():
            try:
                img = PIL.Image.open(observations.mobile_screenshot)
                images.append(img)
            except Exception as e:
                logger.warning(f"Failed to load mobile screenshot: {e}")
        
        # Call Gemini with images and prompt
        try:
            response = self.model.generate_content([prompt] + images)
            
            # Parse response
            result = self._parse_evaluation_response(response.text, observations)
            
            logger.info(f"   ✅ Evaluation complete:")
            logger.info(f"      Score: {result.score}/100")
            logger.info(f"      Issues: {len(result.issues)}")
            logger.info(f"      Fix suggestions: {len(result.fix_suggestions)}")
            
            return result
            
        except Exception as e:
            logger.error(f"   Gemini analysis failed: {e}")
            
            # Return fallback evaluation
            return EvaluationResult(
                score=50,
                passed=False,
                category_scores={cat: 0 for cat in rubric.keys()},
                issues=[
                    EvaluationIssue(
                        category="robustness",
                        severity="high",
                        description=f"Evaluation failed: {str(e)}",
                        repro_steps=["Load page"]
                    )
                ],
                fix_suggestions=["Fix evaluation errors"],
                observations=observations,
                feedback=f"Evaluation error: {str(e)}"
            )
    
    def _build_evaluation_prompt(
        self,
        task: str,
        observations: BrowserObservation,
        rubric: Dict[str, Any]
    ) -> str:
        """Build comprehensive evaluation prompt"""
        
        # Build rubric description
        rubric_desc = "EVALUATION RUBRIC:\n"
        for category, details in rubric.items():
            weight = details["weight"]
            desc = details["description"]
            rubric_desc += f"\n{category.upper()} ({weight} points): {desc}\n"
            for criterion in details["criteria"]:
                rubric_desc += f"  - {criterion}\n"
        
        # Build observations summary
        obs_summary = f"""
BROWSER OBSERVATIONS:

Desktop Screenshot: {"✅ Captured" if observations.desktop_screenshot else "❌ Missing"}
Mobile Screenshot (375px): {"✅ Captured" if observations.mobile_screenshot else "❌ Missing"}

Interactions Performed:
{chr(10).join(f"  - {action}" for action in observations.interactions_performed)}

Interaction Results:
{chr(10).join(f"  - {name}: {'✅ Success' if result else '❌ Failed'}" for name, result in observations.interaction_results.items())}

Console Logs: {len(observations.console_logs)} total
Console Errors: {len(observations.console_errors)} errors
{chr(10).join(f"  - {err.get('message', 'Unknown error')}" for err in observations.console_errors[:5])}

DOM Snapshot:
  - Title: {observations.dom_snapshot.get('title', 'N/A') if observations.dom_snapshot else 'N/A'}
  - Buttons: {len(observations.dom_snapshot.get('buttons', [])) if observations.dom_snapshot else 0}
"""
        
        prompt = f"""You are a senior QA engineer performing comprehensive browser testing.

ORIGINAL TASK:
{task}

{rubric_desc}

{obs_summary}

IMAGES PROVIDED:
- Desktop screenshot (1440x900)
- Mobile screenshot (375px) if available

YOUR EVALUATION TASK:

Analyze the screenshots and observations to evaluate the implementation against the rubric.

Provide your evaluation in this EXACT JSON format:

{{
  "functionality": {{
    "score": <0-25>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "visual_design": {{
    "score": <0-25>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "ux": {{
    "score": <0-15>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "accessibility": {{
    "score": <0-15>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "responsiveness": {{
    "score": <0-15>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "robustness": {{
    "score": <0-5>,
    "passed": <true/false>,
    "issues": ["issue1", "issue2"]
  }},
  "total_score": <0-100>,
  "passed": <true/false>,
  "detailed_issues": [
    {{
      "category": "functionality",
      "severity": "high",
      "description": "Button does not respond to clicks",
      "repro_steps": ["1. Click the submit button", "2. Nothing happens"]
    }}
  ],
  "fix_suggestions": [
    "Add click event handler to submit button",
    "Improve color contrast for accessibility",
    "Add responsive styles for mobile"
  ],
  "feedback": "Overall assessment and key points..."
}}

SCORING GUIDELINES:
- 90-100: Excellent, production ready
- 70-89: Good, minor improvements needed
- 50-69: Acceptable, significant work needed
- 0-49: Poor, major issues

IMPORTANT:
- Return ONLY valid JSON, no markdown formatting
- Be specific in issues and repro steps
- Provide actionable fix suggestions
- Consider both screenshots in your evaluation
- Passing threshold: 70/100

Generate the evaluation now:
"""
        
        return prompt
    
    def _parse_evaluation_response(
        self,
        response_text: str,
        observations: BrowserObservation
    ) -> EvaluationResult:
        """Parse Gemini's evaluation response"""
        
        # Clean response
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        try:
            data = json.loads(text)
            
            # Extract category scores - include visual_design
            category_scores = {}
            for category in ["functionality", "visual_design", "ux", "accessibility", "responsiveness", "robustness"]:
                if category in data:
                    category_scores[category] = data[category].get("score", 0)
            
            # Parse detailed issues
            issues = []
            for issue_data in data.get("detailed_issues", []):
                issues.append(EvaluationIssue(
                    category=issue_data.get("category", "unknown"),
                    severity=issue_data.get("severity", "medium"),
                    description=issue_data.get("description", ""),
                    repro_steps=issue_data.get("repro_steps", []),
                    screenshot_reference=observations.desktop_screenshot
                ))
            
            # Extract fix suggestions
            fix_suggestions = data.get("fix_suggestions", [])
            
            # Calculate total score
            total_score = data.get("total_score", sum(category_scores.values()))
            
            return EvaluationResult(
                score=total_score,
                passed=total_score >= 70,
                category_scores=category_scores,
                issues=issues,
                fix_suggestions=fix_suggestions,
                observations=observations,
                feedback=data.get("feedback", "")
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse evaluation response: {e}")
            
            # Return fallback
            return EvaluationResult(
                score=50,
                passed=False,
                category_scores={
                    "functionality": 10,
                    "visual_design": 10,
                    "ux": 10,
                    "accessibility": 10,
                    "responsiveness": 10,
                    "robustness": 10
                },
                issues=[
                    EvaluationIssue(
                        category="robustness",
                        severity="high",
                        description="Evaluation parsing failed",
                        repro_steps=["Failed to parse Gemini response"]
                    )
                ],
                fix_suggestions=["Review evaluation response format"],
                observations=observations,
                feedback="Failed to parse evaluation. Please review manually."
            )
    
    def to_dict(self, result: EvaluationResult) -> Dict[str, Any]:
        """Convert evaluation result to dictionary"""
        
        return {
            "score": result.score,
            "passed": result.passed,
            "category_scores": result.category_scores,
            "issues": [
                {
                    "category": issue.category,
                    "severity": issue.severity,
                    "description": issue.description,
                    "repro_steps": issue.repro_steps,
                    "screenshot_reference": issue.screenshot_reference
                }
                for issue in result.issues
            ],
            "fix_suggestions": result.fix_suggestions,
            "feedback": result.feedback,
            "observations": {
                "desktop_screenshot": result.observations.desktop_screenshot,
                "mobile_screenshot": result.observations.mobile_screenshot,
                "console_errors": len(result.observations.console_errors),
                "interactions_performed": result.observations.interactions_performed,
                "interaction_results": result.observations.interaction_results
            }
        }
