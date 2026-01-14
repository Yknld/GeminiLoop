# Evaluator Upgrade - Gemini-Controlled Browser QA

## Overview

The evaluator has been upgraded to a comprehensive "Gemini-controlled browser QA" system that performs interactive testing and structured evaluation.

## What Changed

### Before
- Simple screenshot + console log analysis
- Basic scoring without categories
- No interaction testing
- Single viewport

### After
- **Interactive browser testing** with MCP tools
- **Structured rubric** with 5 categories
- **Multi-viewport testing** (desktop + mobile)
- **Detailed issues** with repro steps
- **Fix suggestions** for patches
- **Robust error handling**

---

## New Architecture

```
User Request
    ↓
evaluate(url, mcp_client, task, screenshots_dir)
    ↓
┌─────────────────────────────────────────────┐
│  Phase 1: Collect Browser Observations     │
├─────────────────────────────────────────────┤
│  1. Navigate to URL                         │
│  2. Take desktop screenshot (1440x900)      │
│  3. Get DOM snapshot                        │
│  4. Test interactions:                      │
│     - Click "Start" button (if exists)      │
│     - Click "Begin" button (if exists)      │
│     - Click "Next" button (if exists)       │
│     - Try form submit (if exists)           │
│     - Test first input (if exists)          │
│  5. Resize to mobile (375px)                │
│  6. Take mobile screenshot                  │
│  7. Collect console logs                    │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  Phase 2: Analyze with Gemini              │
├─────────────────────────────────────────────┤
│  1. Upload screenshots to Gemini            │
│  2. Build comprehensive prompt with:        │
│     - Rubric (5 categories)                 │
│     - Observations summary                  │
│     - Interaction results                   │
│  3. Gemini analyzes and returns:            │
│     - Category scores                       │
│     - Detailed issues with repro steps      │
│     - Fix suggestions                       │
│     - Overall feedback                      │
└─────────────────────────────────────────────┘
    ↓
EvaluationResult (structured output)
```

---

## Evaluation Rubric

### 5 Categories (Total: 100 points)

#### 1. Functionality (25 points)
- Core features work as expected
- Interactive elements functional
- User workflows complete
- No JavaScript errors

#### 2. UX (25 points)
- Clear visual hierarchy
- Intuitive navigation
- Appropriate feedback
- Professional appearance

#### 3. Accessibility (20 points)
- Semantic HTML
- ARIA labels
- Keyboard navigation
- Good contrast

#### 4. Responsiveness (20 points)
- Mobile layout usable
- Desktop optimal
- No horizontal scrolling
- Adequate touch targets

#### 5. Robustness (10 points)
- No console errors
- Error handling
- Stable functionality
- Handles edge cases

**Passing Score:** 70/100

---

## Interactive Testing

The evaluator now **actively interacts** with the page:

### Tested Interactions

```javascript
// Button interactions
- 'button:has-text("Start")'
- 'button:has-text("Begin")'
- 'button:has-text("Next")'
- 'button[type="submit"]'
- '.cta-button'

// Input testing
- 'input:first-of-type' → Fill with "test input"

// Link testing
- 'a:first-of-type' → Check existence
```

### Robust Handling
- ✅ Gracefully handles missing elements
- ✅ Try/catch around all interactions
- ✅ Logs success/failure for each test
- ✅ Continues even if interactions fail

---

## Multi-Viewport Screenshots

### Desktop View
- **Resolution:** 1440x900
- **File:** `screenshots/iter_N/desktop.png`
- **Purpose:** Primary evaluation view

### Mobile View  
- **Resolution:** 375x667
- **File:** `screenshots/iter_N/mobile.png`
- **Purpose:** Responsiveness testing

Both screenshots are uploaded to Gemini for analysis.

---

## Structured Output

### EvaluationResult

```python
@dataclass
class EvaluationResult:
    score: int  # 0-100
    passed: bool  # True if >= 70
    category_scores: Dict[str, int]
    issues: List[EvaluationIssue]
    fix_suggestions: List[str]
    observations: BrowserObservation
    feedback: str
```

### EvaluationIssue

```python
@dataclass
class EvaluationIssue:
    category: str  # functionality, ux, accessibility, etc.
    severity: str  # critical, high, medium, low
    description: str  # What's wrong
    repro_steps: List[str]  # How to reproduce
    screenshot_reference: str  # Which screenshot shows it
```

### BrowserObservation

```python
@dataclass
class BrowserObservation:
    desktop_screenshot: str
    mobile_screenshot: str
    console_logs: List[Dict]
    console_errors: List[Dict]
    dom_snapshot: Dict
    interactions_performed: List[str]
    interaction_results: Dict[str, bool]
```

---

## Example Output

### Console Output

```
🧠 Phase 3: Comprehensive Evaluation
----------------------------------------------------------------------
🧠 Starting Gemini-controlled browser QA
   URL: file:///path/to/site/index.html

📊 Collecting browser observations...
   Navigating to: file:///path/to/site/index.html
   Taking desktop screenshot (1440x900)...
   Getting DOM snapshot...
   Testing: button_start (button:has-text("Start"))
      ✅ Clicked button_start
   Testing: button_next (button:has-text("Next"))
      ℹ️  button_next not found
   Testing: input_first (input:first-of-type)
      ✅ Filled input_first
   Testing mobile responsiveness (375px)...
   Collecting console logs...
   ✅ Observations collected:
      Interactions: 8
      Screenshots: 2
      Console errors: 0

🤖 Analyzing with Gemini...
   ✅ Evaluation complete:
      Score: 82/100
      Issues: 3
      Fix suggestions: 5

   Score: 82/100
   Status: ✅ PASSED
   Time: 5.2s

   Category Scores:
   ✅ functionality: 22/25
   ✅ ux: 20/25
   ❌ accessibility: 14/20
   ✅ responsiveness: 18/20
   ✅ robustness: 8/10

   Key Issues (3):
   1. [medium] Missing ARIA labels on form inputs
   2. [low] Button hover state could be more pronounced
   3. [low] Mobile spacing could be improved

   Fix Suggestions (5):
   1. Add aria-label attributes to all form inputs
   2. Enhance button hover effects with scale transform
   3. Increase mobile padding for better touch targets
   ...
```

### Saved Artifacts

```
/runs/<run_id>/artifacts/
├── evaluation_iter_1.json
└── screenshots/
    └── iter_1/
        ├── desktop.png
        └── mobile.png
```

### evaluation.json

```json
{
  "score": 82,
  "passed": true,
  "category_scores": {
    "functionality": 22,
    "ux": 20,
    "accessibility": 14,
    "responsiveness": 18,
    "robustness": 8
  },
  "issues": [
    {
      "category": "accessibility",
      "severity": "medium",
      "description": "Missing ARIA labels on form inputs",
      "repro_steps": [
        "1. Inspect form inputs in DOM",
        "2. Note absence of aria-label attributes"
      ],
      "screenshot_reference": "/path/to/desktop.png"
    }
  ],
  "fix_suggestions": [
    "Add aria-label attributes to all form inputs",
    "Enhance button hover effects with scale transform",
    "Increase mobile padding for better touch targets"
  ],
  "feedback": "Overall, the implementation is solid with good functionality and UX. Main improvements needed in accessibility.",
  "observations": {
    "desktop_screenshot": "/path/to/desktop.png",
    "mobile_screenshot": "/path/to/mobile.png",
    "console_errors": 0,
    "interactions_performed": [
      "navigate",
      "screenshot_desktop",
      "snapshot",
      "click_button_start",
      "fill_input_first",
      "screenshot_mobile",
      "console_logs"
    ],
    "interaction_results": {
      "navigate": true,
      "click_button_start": true,
      "button_next": false,
      "fill_input_first": true
    }
  }
}
```

---

## Integration with OpenHands

The fix suggestions from the evaluator are now passed to the patch generator:

```python
patch_plan = generate_patch_plan(evaluation, task, files)
patch_plan["fix_suggestions_from_evaluator"] = evaluation_result.fix_suggestions
```

This ensures OpenHands knows exactly what to fix based on Gemini's analysis.

---

## Rubric Schema (JSON)

```json
{
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
  "ux": {
    "weight": 25,
    "description": "User experience is intuitive and pleasant",
    "criteria": [
      "Clear visual hierarchy",
      "Intuitive navigation and flow",
      "Appropriate feedback for user actions",
      "Professional and polished appearance"
    ]
  },
  "accessibility": {
    "weight": 20,
    "description": "Accessible to all users",
    "criteria": [
      "Semantic HTML elements",
      "Proper ARIA labels where needed",
      "Keyboard navigation works",
      "Good color contrast"
    ]
  },
  "responsiveness": {
    "weight": 20,
    "description": "Works well on different screen sizes",
    "criteria": [
      "Mobile layout (375px) is usable",
      "Desktop layout is optimal",
      "No horizontal scrolling on mobile",
      "Touch targets are adequate"
    ]
  },
  "robustness": {
    "weight": 10,
    "description": "Handles edge cases and errors gracefully",
    "criteria": [
      "No console errors",
      "Graceful error handling",
      "No broken functionality",
      "Stable under interaction"
    ]
  }
}
```

---

## API Changes

### Old API

```python
evaluation = await evaluator.evaluate(
    task=task,
    screenshot_path=screenshot_path,
    page_snapshot=page_snapshot,
    console_errors=console_errors
)
```

### New API

```python
evaluation_result = await evaluator.evaluate(
    url=preview_url,  # File or HTTP URL
    mcp_client=mcp,   # MCP client for interactions
    task=task,
    screenshots_dir=screenshots_dir,  # Where to save screenshots
    rubric=None  # Optional custom rubric
)

# Convert to dict for storage
evaluation_dict = evaluator.to_dict(evaluation_result)
```

---

## Error Handling

### Robust Try/Catch

Every interaction is wrapped in try/catch:

```python
try:
    await mcp_client.call_tool("browser_click", {"selector": selector})
    observation.interaction_results[test_name] = True
except Exception as e:
    logger.info(f"⚠️  {test_name} interaction failed: {e}")
    observation.interaction_results[test_name] = False
```

### Fallback Evaluation

If Gemini analysis fails:
- Returns score of 50
- Marks as failed
- Includes error in feedback
- Still saves observations

### Missing Screenshots

If screenshots fail:
- Logs error
- Continues evaluation
- Uses available observations
- Gemini works with what's available

---

## Performance

### Typical Timings

```
Browser observations: 3-5s
  - Navigation: 1s
  - Desktop screenshot: 0.5s
  - Interactions: 1-2s
  - Mobile resize + screenshot: 1s
  - Console logs: 0.5s

Gemini analysis: 3-5s
  - Image upload: 1s
  - Analysis: 2-4s

Total: 6-10s per evaluation
```

---

## Testing

```bash
# Test new evaluator
python -m orchestrator.main "Create a quiz app"

# Check evaluation output
cat runs/<run_id>/artifacts/evaluation_iter_1.json | jq

# View screenshots
open runs/<run_id>/artifacts/screenshots/iter_1/desktop.png
open runs/<run_id>/artifacts/screenshots/iter_1/mobile.png

# Check interaction results
cat runs/<run_id>/artifacts/evaluation_iter_1.json | jq '.observations.interaction_results'
```

---

## Benefits

### For Evaluation
✅ More comprehensive testing  
✅ Multi-viewport coverage  
✅ Interactive functionality verification  
✅ Structured, actionable feedback  

### For Patching
✅ Better fix suggestions for OpenHands  
✅ Specific repro steps  
✅ Severity-based prioritization  
✅ Screenshot references  

### For Debugging
✅ Full interaction history  
✅ Multiple screenshots  
✅ Console log capture  
✅ DOM snapshot  

---

## Future Enhancements

- [ ] Lighthouse score integration
- [ ] Custom interaction scripts per task
- [ ] Video recording of interactions
- [ ] Performance metrics (LCP, FID, CLS)
- [ ] Visual regression testing
- [ ] A11y automated checks (axe-core)

---

## Summary

The evaluator is now a **Gemini-controlled browser QA** system that:
- ✅ Interacts with pages like a real user
- ✅ Tests across multiple viewports
- ✅ Uses a comprehensive rubric
- ✅ Provides structured, actionable feedback
- ✅ Handles errors gracefully
- ✅ Integrates seamlessly with OpenHands patching

**Result:** Much higher quality evaluations and better patch suggestions!
