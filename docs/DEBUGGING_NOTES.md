# Debugging Notes

## Common Failure Modes

### 1. Empty Candidates from Gemini (`IndexError: list index out of range`)

**Symptom:**
```
IndexError: list index out of range
response.candidates[0]
```

**Cause:** Gemini returns empty `candidates` list or response with no content parts.

**Fix Applied:**
- Added `_safe_extract_response_parts()` helper that safely checks for candidates/content
- Soft recovery: take safe default action (scroll/snapshot) and continue
- After 3 consecutive failures, gracefully end exploration

**Prevention:**
- Always use `_safe_extract_response_parts()` instead of directly accessing `response.candidates[0]`
- Check `has_content` before processing

### 2. Visible Text Slice Error (`slice(None, 1500, None)`)

**Symptom:**
```
Failed to get visible text: slice(None, 1500, None)
TypeError: 'NoneType' object is not subscriptable
```

**Cause:** `mcp_client.evaluate("document.body.innerText")` returns non-string (None/list/dict) instead of string.

**Fix Applied:**
- Added type checking and coercion in `_get_browser_state()`
- Handles: str (passthrough), list (join first 50), dict (JSON stringify), None (empty string)
- Never crashes on unexpected return types

**Prevention:**
- Always coerce `evaluate()` results to string before slicing
- Add logging when unexpected types are encountered

### 3. Terminal Tool Soft Timeout (Exit Code 130)

**Symptom:**
```
⏳ Process still running (soft timeout)
❌ Exit code: 130  # (Ctrl+C signal)
```

**Cause:** OpenHands terminal tool runs long-running commands (like dev servers) without hard timeout.

**Status:** OpenHands SDK manages this internally. Exit code 130 is treated as "cancelled" not "failed".

**Workaround:**
- OpenHands agent should detect long-running processes and not wait
- Dev servers should be started in background if needed

### 4. Function Response Send Failures

**Symptom:**
```
InvalidArgument: 400 Please ensure that the number of function response parts is equal to the number of function call parts
```

**Cause:** Gemini makes multiple function calls in one turn, but we send mismatched number of responses.

**Fix Applied:**
- Send `FunctionResponse` for EVERY function call Gemini makes (even if only first is executed)
- Added retry logic: if send fails, retry once with minimal payload
- If retry fails, increment failure counter and continue (don't crash)

**Prevention:**
- Always match 1:1 function calls to function responses
- Use try/except around `chat.send_message()` for function responses

## Artifacts Locations

### During Execution

**Per-iteration artifacts:**
```
/runpod-volume/runs/runs/{run_id}/artifacts/
├── screenshots/
│   └── iter_{N}/
│       ├── step_1_before.png       # Before each action
│       ├── step_1_after.png        # After each action
│       ├── step_2_before.png
│       └── ... 
├── step_1_observation.json         # DOM state, text, targets per step
├── step_2_observation.json
├── agentic_exploration.json        # Full exploration log
└── generation_prompt_{timestamp}.txt
```

**Timeout artifacts (when terminal hangs):**
- Logged in stderr/stdout of OpenHands execution
- No separate artifact saved for timeouts currently

### After Job Completion

**Local extraction:**
```
/tmp/{task_name}/
└── index.html  # Final generated page
```

## How to Reproduce Locally

### Test Agentic Evaluator

```bash
cd /Users/danielntumba/match-me/GeminiLoop

# Set environment
export GOOGLE_AI_STUDIO_API_KEY="your_key"
export EVALUATOR_MODEL="gemini-3-flash-preview"
export AGENTIC_EVAL="true"
export AGENTIC_MAX_STEPS="10"

# Run isolated test (requires Playwright + Gemini SDK)
python3 -c "
import asyncio
from orchestrator.agentic_evaluator import AgenticEvaluator
from orchestrator.mcp_real_client import PlaywrightMCPClient
from pathlib import Path

async def test():
    client = PlaywrightMCPClient()
    await client.connect()
    
    evaluator = AgenticEvaluator(max_steps=5)
    result = await evaluator.evaluate_page(
        url='http://localhost:8000/index.html',
        mcp_client=client,
        task='Test interactive calculator',
        artifacts_dir=Path('./test_artifacts')
    )
    
    print(f'Score: {result.score}/100')
    await client.disconnect()

asyncio.run(test())
"
```

### Test on RunPod

```bash
# Submit job
export RUNPOD_API_KEY="rpa_..."
curl -X POST https://api.runpod.ai/v2/g31a5b3hwccqlm/run \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {"task": "Create a calculator app"}}'

# Check status
JOB_ID="..."
curl https://api.runpod.ai/v2/g31a5b3hwccqlm/status/$JOB_ID \
  -H "Authorization: Bearer $RUNPOD_API_KEY"
```

### View Live Progress (VNC)

Not available currently - logs only. VNC removed due to ngrok payment requirements.

## Key Code Locations

### Agentic Evaluator
- **Main file:** `orchestrator/agentic_evaluator.py`
- **Safe parsing:** `_safe_extract_response_parts()` (line ~317)
- **Exploration loop:** `_run_exploration_loop()` (line ~367)
- **Visible text:** `_get_browser_state()` (line ~751)

### Browser Client
- **File:** `orchestrator/mcp_real_client.py`
- **Evaluate method:** `evaluate()` (line ~197)

### OpenHands Integration
- **File:** `orchestrator/openhands_client.py`
- **Code generation:** `generate_code()` (line ~116)
- **Terminal tool:** Used via OpenHands SDK internally

## Error Recovery Strategy

### Soft Recovery (Continue Execution)
1. Empty Gemini response → Default action (scroll/snapshot)
2. Tool response send failure → Retry once, then continue
3. Unexpected visible text type → Coerce to string, log warning
4. Missing interactive targets → Return empty list

### Hard Stop (End Exploration)
1. 3+ consecutive empty responses
2. 3+ consecutive tool response send failures
3. 3+ consecutive step execution exceptions

### No Recovery (Informational Only)
1. Screenshot load failures → Log warning, continue
2. Console error retrieval failure → Return empty list
3. Dialog detection injection failure → Log warning, continue
