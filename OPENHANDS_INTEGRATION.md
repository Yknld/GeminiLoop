# OpenHands Integration

GeminiLoop now includes OpenHands integration for automated code patching based on evaluation feedback.

## Overview

When an evaluation fails (score < 70), the orchestrator:
1. Generates a patch plan from evaluation feedback
2. Calls OpenHands to apply fixes
3. Re-runs the evaluation (max 2 iterations total for MVP)

## Architecture

```
Evaluation Failed (score < 70)
        ↓
Generate Patch Plan (from feedback)
        ↓
Apply Patch via OpenHands
        ↓
Copy patched files to site/
        ↓
Re-evaluate
        ↓
Pass or Fail
```

## Components

### 1. OpenHandsClient (Base Interface)

```python
class OpenHandsClient(ABC):
    @abstractmethod
    def apply_patch_plan(self, workspace_path: str, patch_plan: dict) -> dict:
        """Apply patches to workspace"""
        pass
```

### 2. MockOpenHandsClient (Demo/Testing)

**Purpose:** Regex-based edits for demo without requiring OpenHands CLI

**Features:**
- Simple find/replace operations
- Natural language change parsing (best effort)
- Generic improvements based on feedback
- File creation/modification/deletion

**Example:**
```python
patch_plan = {
    "instructions": "Improve button styling",
    "files": [
        {
            "path": "index.html",
            "action": "modify",
            "description": "Fix button colors",
            "changes": [
                {"find": "padding: 8px", "replace": "padding: 12px 24px"}
            ]
        }
    ]
}

client = MockOpenHandsClient(artifacts_dir)
result = client.apply_patch_plan(workspace_path, patch_plan)
```

### 3. LocalSubprocessOpenHandsClient (Production)

**Purpose:** Run actual OpenHands CLI as subprocess

**Requirements:**
- OpenHands CLI installed: `pip install openhands`
- Running in same container (no Docker-in-Docker)

**Features:**
- Runs `openhands run --workspace /path --instructions file.txt`
- Captures stdout/stderr to artifacts
- 5-minute timeout
- Full OpenHands capabilities

**Example:**
```python
client = LocalSubprocessOpenHandsClient(artifacts_dir)
result = client.apply_patch_plan(workspace_path, patch_plan)

# Result includes:
# - success: bool
# - files_modified: List[str]
# - stdout/stderr: str
# - duration_seconds: float
```

## Configuration

Set via environment variable:

```bash
# Mock mode (default) - regex-based demo
export OPENHANDS_MODE=mock

# Local mode - subprocess CLI
export OPENHANDS_MODE=local
```

Or in `.env`:
```
OPENHANDS_MODE=mock
```

## Patch Plan Structure

```json
{
  "instructions": "High-level instructions for OpenHands",
  "files": [
    {
      "path": "index.html",
      "action": "modify",
      "description": "What to fix",
      "changes": [
        "Specific change 1",
        "Specific change 2"
      ]
    }
  ],
  "original_score": 55,
  "issues_count": 3
}
```

## Patch Generator

Automatically creates patch plans from evaluation feedback:

```python
from orchestrator.patch_generator import generate_patch_plan

patch_plan = generate_patch_plan(
    evaluation={
        "score": 55,
        "feedback": "Button styling needs work",
        "visual": {
            "issues": ["Poor colors", "Bad spacing"]
        }
    },
    task="Create a landing page",
    files_generated={"index.html": "/path/index.html"}
)
```

**Features:**
- Extracts issues from evaluation categories
- Generates actionable change descriptions
- Prioritizes issues by severity
- Creates file-specific instructions

## Usage

### Basic Run with OpenHands

```bash
# Set mode
export OPENHANDS_MODE=mock

# Run orchestrator
python -m orchestrator.main "Create a beautiful landing page"

# Output includes:
# 📝 ITERATION 1
# 🎨 Generation
# 🌐 Testing
# 🧠 Evaluation → Score: 55/100 ❌

# 🔧 Phase 4: OpenHands Patch Application
# 📝 Generating patch plan...
# ✅ Patch plan generated: patch_plan_iter_1.json
# 🔧 Applying patch via OpenHands...
# ✅ Patch applied successfully
# 📋 Copying patched files to site...

# 📝 ITERATION 2
# 🌐 Testing (re-evaluation)
# 🧠 Evaluation → Score: 78/100 ✅
```

### Artifacts Generated

Each run with OpenHands produces:

```
/runs/<run_id>/artifacts/
  ├── patch_plan_iter_1.json      # Generated patch plan
  ├── patch_result_iter_1.json    # Patch application result
  ├── mock_openhands_*.log        # Mock client log (mock mode)
  ├── openhands_stdout_*.log      # OpenHands output (local mode)
  ├── openhands_stderr_*.log      # OpenHands errors (local mode)
  └── index.html.backup           # Backup of original file
```

## Trace Events

OpenHands operations are logged to `trace.jsonl`:

```jsonl
{"event_type": "info", "message": "Patch plan generated", "data": {"files_count": 1, "issues_count": 3}}
{"event_type": "info", "message": "Patch applied", "data": {"success": true, "files_modified": ["index.html"]}}
```

## Testing

```bash
# Test OpenHands components
python test_openhands.py

# Test full loop with mock mode
export OPENHANDS_MODE=mock
python -m orchestrator.main "Create a simple page"

# Test with local mode (requires OpenHands CLI)
export OPENHANDS_MODE=local
python -m orchestrator.main "Create a simple page"
```

## Mock Client Capabilities

The `MockOpenHandsClient` supports:

### 1. Direct Find/Replace
```python
"changes": [
    {"find": "color: red", "replace": "color: blue"}
]
```

### 2. Natural Language (Best Effort)
- "Change color to blue" → Updates color CSS
- "Make font larger" → Increases font-size
- "Add button styling" → Injects button CSS
- "Fix button styling" → Improves button styles

### 3. Generic Improvements
Based on description keywords:
- "style" / "design" → Adds transitions, improves spacing
- "error" / "bug" → Fixes unclosed tags
- "color" → Updates color scheme

## Local Client Setup

For production use with actual OpenHands:

```bash
# Install OpenHands CLI
pip install openhands

# Verify installation
which openhands

# Set mode
export OPENHANDS_MODE=local

# Run
python -m orchestrator.main "Your task"
```

**Note:** The actual OpenHands CLI interface may vary. The current implementation assumes:
```bash
openhands run --workspace /path --instructions file.txt --no-interactive
```

Adjust `LocalSubprocessOpenHandsClient._apply_patch_plan()` based on actual OpenHands CLI.

## Limitations (MVP)

1. **Max 2 iterations total** - After initial generation + 1 patch attempt
2. **No Docker-in-Docker** - Runs in same container only
3. **No GitHub integration** - Files remain local
4. **Simple patch plans** - Based on evaluation feedback only
5. **Mock mode is basic** - Regex-based, not AI-powered

## Future Enhancements

- [ ] Multi-iteration patching (configurable max_patch_attempts)
- [ ] GitHub PR creation after successful patch
- [ ] Docker-in-Docker support for isolated OpenHands
- [ ] More sophisticated patch plan generation (using Gemini)
- [ ] Rollback mechanism for failed patches
- [ ] Diff visualization in view.html
- [ ] Patch plan validation before application

## Error Handling

If OpenHands fails:
- Error is logged to trace
- Patch result saved with error details
- Orchestrator continues to next iteration
- Run completes normally (marks as completed, not failed)

## Performance

Typical timing (mock mode):
- Patch plan generation: < 1s
- Mock patch application: < 1s
- Re-evaluation: 3-5s

Typical timing (local mode):
- Patch plan generation: < 1s
- OpenHands execution: 10-60s (depends on changes)
- Re-evaluation: 3-5s

## Debugging

View patch details:
```bash
# View patch plan
cat runs/<run_id>/artifacts/patch_plan_iter_1.json | jq

# View patch result
cat runs/<run_id>/artifacts/patch_result_iter_1.json | jq

# View OpenHands logs (local mode)
cat runs/<run_id>/artifacts/openhands_stdout_*.log

# View mock logs (mock mode)
cat runs/<run_id>/artifacts/mock_openhands_*.log

# View trace
cat runs/<run_id>/artifacts/trace.jsonl | grep -i patch
```

## Example End-to-End Flow

```python
# 1. Initial generation
generator.generate(task) → creates index.html

# 2. Test & evaluate
mcp.screenshot() → screenshot.png
evaluator.evaluate() → score: 55/100, feedback: "Button needs styling"

# 3. Generate patch plan
patch_plan = generate_patch_plan(evaluation, task, files)
# → {files: [{path: "index.html", changes: ["improve button"]}]}

# 4. Apply patch
openhands.apply_patch_plan(workspace, patch_plan)
# → Mock: applies regex changes
# → Local: runs OpenHands CLI

# 5. Copy to site
workspace/index.html → site/index.html

# 6. Re-evaluate
mcp.screenshot() → screenshot_iter_2.png
evaluator.evaluate() → score: 78/100 ✅

# 7. Complete
report.json saved with full history
```

## Summary

✅ OpenHands integration complete
✅ Two implementations (mock + local)
✅ Automatic patch plan generation
✅ Re-evaluation loop
✅ Full tracing and artifact storage
✅ Environment-based configuration
✅ No Docker-in-Docker required

The loop now works end-to-end with OpenHands in either mock or local mode!
