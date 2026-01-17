# Agentic Evaluator

## Overview

The `AgenticEvaluator` enables Gemini to autonomously explore and test web pages using MCP browser tools. Unlike scripted tests, Gemini sees the actual rendered page through screenshots and makes intelligent decisions about what to test and how to verify functionality.

## Key Improvements

### 1. Multimodal Exploration Loop
- **Truly sees the page**: Each observation step sends a PIL.Image screenshot directly to Gemini
- **Visual verification**: Gemini can confirm buttons work, content appears, and UI updates correctly
- **Evidence-based testing**: Decisions based on actual visual state, not just text descriptions

### 2. Robust Function Calling
- **Multi-part parsing**: Handles responses with both reasoning text and function calls
- **Defensive argument handling**: Safely processes None args, missing fields
- **Multiple function call detection**: Logs warning and executes first call when multiple detected

### 3. Expanded Toolset

**Core Tools:**
- `browser_click`: Click elements using CSS selectors
- `browser_type`: Type text into input fields
- `browser_scroll`: Scroll page up/down
- `browser_evaluate`: Execute arbitrary JavaScript

**New Tools:**
- `browser_wait_for`: Wait for selector/text to appear with timeout
- `browser_hover`: Hover over elements to reveal tooltips/effects
- `browser_press_key`: Press keyboard keys (Enter, Tab, Escape, etc.)
- `browser_get_url`: Get current page URL (verify navigation)
- `browser_dom_snapshot`: Get concise interactive element list
- `finish_exploration`: Signal completion with summary

### 4. Structured Verification

**Before/After Signals:**
- DOM signature hash (text content + element counts + URL)
- Visible text snapshot (first 1500 chars)
- Console errors diff
- Dialog detection

**Verification Process:**
1. Capture BEFORE state (screenshot, DOM sig, text, console)
2. Execute action
3. Wait 500ms
4. Capture AFTER state
5. Compute changes (dom_changed, text_changed, new_errors)
6. Include verification in observation for next step

### 5. Interactive Element Discovery

**Stable Selector Strategy:**
1. Prefer `#id` if available
2. Fallback to `[data-testid="..."]`
3. Try `tag[aria-label="..."]`
4. Use `tag[name="..."]`
5. Last resort: `tag.firstClass`

**Returns:**
- Ranked list of visible, actionable elements (top 15 shown)
- Includes: selector, tag, role, text content, type
- Filters out invisible elements

### 6. Dialog Detection

**Early Injection:**
After page load, injects JavaScript to:
- Wrap `window.alert` → records call, returns immediately (no blocking)
- Wrap `window.confirm` → records call, returns false
- Wrap `window.prompt` → records call, returns null
- Disable `window.onbeforeunload`

**Recording:**
All dialog attempts stored in `window.__dialogCalls` array with:
- type (alert/confirm/prompt/beforeunload)
- message
- timestamp

**Impact:**
Dialogs detected = UX score penalty (system dialogs indicate poor design)

### 7. Rubric Consistency

**Fixed Issues:**
- Category score ranges now match rubric weights exactly
- Prompt explicitly states max points per category
- JSON schema matches EvaluationResult structure
- Score must equal sum of category scores

**Rubric:**
- Functionality: 25 points
- Visual Design: 25 points
- UX: 15 points
- Accessibility: 15 points
- Responsiveness: 15 points
- Robustness: 5 points
- **Total: 100 points**

### 8. Fair Evaluation Policy

**Harsh but Fair:**
- ✅ Feature works: Agent interacted AND saw expected changes
- ❌ Feature broken: Agent tried reasonable interactions AND nothing happened OR errors appeared
- ⚠️ Feature untestable: Couldn't interact (element not found, crashes)

**NOT Penalized:**
- Features the agent couldn't find (but should be)
- Interactions not attempted (agent didn't think to test)

**Penalized:**
- Verified broken functionality
- Console errors detected during testing
- System dialogs triggered
- Missing features explicitly mentioned in task

## Observe → Act Loop

### Step Flow

```
1. OBSERVE (BEFORE)
   ├─ Take screenshot (step_N_before.png)
   ├─ Get visible text (first 1500 chars)
   ├─ Discover interactive targets (with stable selectors)
   ├─ Check console errors
   ├─ Compute DOM signature hash
   ├─ Check for dialogs
   └─ Get current URL

2. SEND MULTIMODAL OBSERVATION
   ├─ Text: formatted observation with targets, errors, dialogs
   └─ Image: PIL.Image loaded from screenshot

3. GEMINI CHOOSES ACTION
   ├─ Reasoning text (optional)
   └─ Function call (tool + args)

4. EXECUTE ACTION
   ├─ Run tool (click, type, scroll, evaluate, etc.)
   └─ Wait 500ms

5. VERIFY (AFTER)
   ├─ Take screenshot (step_N_after.png)
   ├─ Capture same signals as BEFORE
   ├─ Compute changes: dom_changed, text_changed, new_errors
   └─ Detect new dialogs

6. LOG & SEND RESULT
   ├─ Save step to exploration_log with full context
   ├─ Save step_N_observation.json
   └─ Send tool result + verification to Gemini

7. REPEAT (max 15 steps or finish_exploration)
```

## Artifacts Saved

### Per-Step Artifacts
- `step_N_before.png` - Screenshot before action
- `step_N_after.png` - Screenshot after action
- `step_N_observation.json` - Text, targets, errors, verification signals

### Summary Artifacts
- `agentic_exploration.json` - Complete log with:
  - All steps: tool, args, reasoning, before/after states, verification
  - Total steps taken
  - Completion reason (agent_finished / max_steps_reached)
  - Final evaluation result

## False Negative Prevention

### Root Causes Fixed

**1. No Vision in Loop**
- ❌ Before: Only sent text description
- ✅ Now: Sends PIL.Image screenshot each step

**2. No Verification**
- ❌ Before: Agent clicked but couldn't confirm if it worked
- ✅ Now: Captures before/after, computes dom_changed, text_changed

**3. Weak Toolset**
- ❌ Before: Only click, type, scroll, evaluate
- ✅ Now: Added wait_for, hover, press_key, get_url, dom_snapshot

**4. Fragile Parsing**
- ❌ Before: Assumed single function_call part
- ✅ Now: Iterates all parts, collects reasoning + multiple calls

**5. System Dialogs**
- ❌ Before: Dialogs could block testing silently
- ✅ Now: Injected detection wrapper, records all attempts

**6. Poor Selectors**
- ❌ Before: Generic "button.class" selectors (unstable)
- ✅ Now: Prefer #id, data-testid, aria-label (stable)

### How It Avoids False Negatives

1. **Vision**: Gemini sees rendered page, can confirm visual changes
2. **Verification**: DOM/text change signals prove interaction worked
3. **Wait Primitives**: Can wait for async content (no race conditions)
4. **Better Selectors**: Stable IDs reduce "element not found" failures
5. **Dialog Detection**: Alerts don't silently block testing
6. **Multiple Attempts**: If first selector fails, sees other targets in list

## Testing Strategy

The agent follows this systematic approach:

1. **Scroll entire page** - See all content, discover all elements
2. **Test each requirement** - Go through task list methodically
3. **Verify each action** - Check if button clicked, input filled, etc.
4. **Document findings** - Note what works/fails with evidence
5. **Test edge cases** - Time permitting (empty inputs, multiple clicks)
6. **Finish with summary** - Detailed report of tested features + results

## Configuration

### Environment Variables
- `GEMINI_MODEL` - Model for agentic control (default: `gemini-2.0-flash-exp`)
- `EVALUATOR_MODEL` - Model for final evaluation (default: `gemini-3-flash-preview`)

### Parameters
- `max_exploration_steps` - Max steps before forcing finish (default: 15)

## Usage

```python
from orchestrator.agentic_evaluator import AgenticEvaluator

evaluator = AgenticEvaluator(max_exploration_steps=15)

result = await evaluator.evaluate(
    url="http://localhost:8000",
    mcp_client=mcp_client,
    task="Build a calculator with +, -, *, / buttons...",
    screenshots_dir=Path("artifacts/screenshots"),
    rubric=EVALUATION_RUBRIC  # optional
)

print(f"Score: {result.score}/100")
print(f"Passed: {result.passed}")
print(f"Issues: {len(result.issues)}")
```

## Limitations

1. **MCP Server Dependency**: Requires Playwright MCP server running
2. **Single Viewport**: Only tests desktop viewport (1440x900) during exploration
3. **JavaScript Only**: Can't test non-JS interactions or pre-JS page state
4. **Sequential Steps**: Doesn't test parallel interactions (e.g., race conditions)
5. **English Bias**: Best for English text; may struggle with non-Latin scripts
6. **Model Constraints**: Limited by Gemini's function calling reliability

## Future Improvements

- Multi-viewport testing (desktop + mobile in exploration loop)
- Network request inspection during actions
- Performance timing (measure action→response latency)
- Visual regression detection (compare screenshots algorithmically)
- Accessibility testing (keyboard nav, screen reader simulation)
- Error recovery (retry failed actions with alternative selectors)
