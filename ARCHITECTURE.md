# GeminiLoop Architecture

## Overview

GeminiLoop is a closed-loop autonomous UI generation and evaluation system with complete run lifecycle management.

## Core Components

### 1. Run State Management

**Files:**
- `orchestrator/run_state.py`

**Purpose:**
Manages the complete lifecycle of a run with type-safe dataclasses.

**Key Classes:**

```python
@dataclass
class RunConfig:
    """Configuration for a run"""
    task: str
    max_iterations: int = 3
    base_dir: Path
    run_id: Optional[str] = None

@dataclass
class IterationResult:
    """Result from a single iteration"""
    iteration: int
    code_generated: Optional[str]
    screenshot_path: Optional[str]
    evaluation: Optional[Dict[str, Any]]
    score: int
    passed: bool
    # ... timing data

@dataclass
class RunResult:
    """Complete result from a run"""
    run_id: str
    status: str  # running, completed, failed
    iterations: List[IterationResult]
    final_score: int
    final_passed: bool
    # ... paths and metadata

class RunState:
    """Manages state for a single run"""
    config: RunConfig
    result: RunResult
    workspace_dir: Path
    artifacts_dir: Path
    site_dir: Path
```

### 2. Trace Logging

**Files:**
- `orchestrator/trace.py`

**Purpose:**
Append-only JSONL trace logging for debugging and observability.

**Format:**
```jsonl
{"event_id": 0, "timestamp": "2026-01-13T...", "event_type": "run_start", ...}
{"event_id": 1, "timestamp": "2026-01-13T...", "event_type": "iteration_start", ...}
{"event_id": 2, "timestamp": "2026-01-13T...", "event_type": "generation_start", ...}
```

**Key Class:**

```python
class TraceLogger:
    """Thread-safe JSONL trace logger"""
    
    def log(self, event_type: TraceEventType, data: Dict, message: str)
    def run_start(self, run_id: str, task: str, config: Dict)
    def iteration_start(self, iteration: int, total: int)
    def generation_end(self, files: list, duration: float)
    # ... event-specific methods
```

**Event Types:**
- `RUN_START` / `RUN_END`
- `ITERATION_START` / `ITERATION_END`
- `GENERATION_START` / `GENERATION_END`
- `TESTING_START` / `TESTING_END`
- `EVALUATION_START` / `EVALUATION_END`
- `SCREENSHOT_TAKEN`
- `ERROR` / `INFO` / `DEBUG`

### 3. Artifacts Management

**Files:**
- `orchestrator/artifacts.py`

**Purpose:**
Structured helpers for saving and managing run artifacts.

**Key Class:**

```python
class ArtifactsManager:
    """Manages artifacts for a run"""
    
    def save_screenshot(self, path: str, iteration: int, metadata: Dict) -> Path
    def save_evaluation(self, evaluation: Dict, iteration: int) -> Path
    def save_log(self, content: str, name: str, log_type: str) -> Path
    def save_file(self, content: str, filename: str, file_type: str) -> Path
    def save_report(self, report: Dict, name: str) -> Path
    
    def get_screenshots(self) -> List[Dict]
    def get_evaluations(self) -> List[Dict]
    def get_latest_screenshot(self) -> Dict
```

**Manifest Structure:**
```json
{
  "screenshots": [...],
  "evaluations": [...],
  "logs": [...],
  "files": [...],
  "reports": [...]
}
```

### 4. Main Orchestrator

**Files:**
- `orchestrator/main.py`

**Purpose:**
Complete run lifecycle orchestration.

**Lifecycle:**

```
1. Setup Phase
   ├─ Create RunConfig
   ├─ Initialize RunState
   ├─ Setup directories (workspace, artifacts, site)
   ├─ Initialize TraceLogger
   ├─ Initialize ArtifactsManager
   └─ Create template HTML

2. Iteration Loop (max_iterations)
   ├─ Phase 1: Code Generation
   │  ├─ Call Gemini generator
   │  ├─ Save code to workspace
   │  ├─ Copy to site for serving
   │  └─ Log generation event
   │
   ├─ Phase 2: Browser Testing
   │  ├─ Connect to Playwright MCP
   │  ├─ Navigate to generated site
   │  ├─ Take screenshot
   │  ├─ Get page snapshot
   │  ├─ Check console errors
   │  └─ Save artifacts
   │
   ├─ Phase 3: Evaluation
   │  ├─ Call Gemini evaluator
   │  ├─ Analyze screenshot + snapshot
   │  ├─ Generate score + feedback
   │  └─ Save evaluation
   │
   └─ Decision
      ├─ If passed → Complete run
      └─ If failed → Next iteration

3. Finalization Phase
   ├─ Complete RunResult
   ├─ Save report.json
   ├─ Save state.json
   ├─ Generate view.html
   └─ Close MCP connection
```

### 5. Code Generation

**Files:**
- `orchestrator/gemini_generator.py`

**Purpose:**
Generate HTML/CSS/JS using Gemini 2.0 Flash.

**Key Class:**

```python
class GeminiCodeGenerator:
    """Gemini-based code generator"""
    
    async def generate(self, task: str, workspace_dir: Path) -> Dict:
        # Returns: {"code": str, "filename": str, "file_path": str}
```

### 6. Evaluation

**Files:**
- `orchestrator/evaluator.py`

**Purpose:**
Evaluate UI quality using Gemini Vision.

**Key Class:**

```python
class GeminiEvaluator:
    """Gemini-based evaluator"""
    
    async def evaluate(
        self,
        task: str,
        screenshot_path: str,
        page_snapshot: Dict,
        console_errors: List
    ) -> Dict:
        # Returns evaluation with score, passed, feedback
```

**Evaluation Rubric:**
```json
{
  "functionality": {
    "score": 0-35,
    "passed": bool,
    "issues": [...]
  },
  "visual": {
    "score": 0-35,
    "passed": bool,
    "issues": [...]
  },
  "errors": {
    "score": 0-30,
    "passed": bool,
    "issues": [...]
  },
  "total_score": 0-100,
  "passed": bool,
  "feedback": "..."
}
```

### 7. MCP Client

**Files:**
- `orchestrator/mcp_real_client.py`
- `orchestrator/playwright_mcp_server.js`

**Purpose:**
JSON-RPC 2.0 communication with Playwright MCP server.

**Protocol:**
```
Python Client <--JSON-RPC--> Node.js Server <--> Playwright/Chromium
    (stdio)                      (subprocess)
```

**Key Methods:**
- `connect()` - Initialize MCP session
- `navigate(url)` - Navigate to URL
- `screenshot(path)` - Take screenshot
- `snapshot()` - Get page snapshot
- `get_console()` - Get console messages

### 8. Preview Server

**Files:**
- `services/preview_server.py`

**Purpose:**
FastAPI server for serving generated sites and run data.

**Endpoints:**
- `GET /` - Server info
- `GET /health` - Health check
- `GET /runs` - List all runs
- `GET /runs/{run_id}` - Get run details
- `GET /preview/{run_id}/` - Serve generated site
- `GET /artifacts/{run_id}/{filename}` - Serve artifacts

## Folder Structure

```
runs/
  └── <run_id>/
      ├── workspace/           # Generated code workspace
      │   └── index.html
      │
      ├── artifacts/           # All run artifacts
      │   ├── trace.jsonl     # Append-only event log
      │   ├── manifest.json   # Artifact manifest
      │   ├── report.json     # Final report
      │   ├── view.html       # Results viewer
      │   ├── screenshot_iter_1.png
      │   ├── screenshot_iter_2.png
      │   ├── evaluation_iter_1.json
      │   └── evaluation_iter_2.json
      │
      ├── site/               # Served HTML files
      │   └── index.html
      │
      └── state.json          # Complete run state
```

## Data Flow

```
1. User Request
   └─> RunConfig(task="...")

2. Setup
   ├─> RunState (creates directories)
   ├─> TraceLogger (trace.jsonl)
   └─> ArtifactsManager (manifest.json)

3. Generation
   ├─> GeminiCodeGenerator
   │   ├─> Gemini API
   │   └─> Returns HTML/CSS/JS
   ├─> Save to workspace/
   └─> Copy to site/

4. Testing
   ├─> PlaywrightMCPClient
   │   ├─> Start Node.js MCP server
   │   ├─> Navigate to file://...
   │   ├─> Take screenshot
   │   └─> Get page snapshot
   └─> Save to artifacts/

5. Evaluation
   ├─> GeminiEvaluator
   │   ├─> Upload screenshot
   │   ├─> Gemini Vision API
   │   └─> Returns score + feedback
   └─> Save to artifacts/

6. Decision
   ├─> If passed: Complete
   └─> If failed: Iterate

7. Finalization
   ├─> Save report.json
   ├─> Save state.json
   ├─> Generate view.html
   └─> Return RunState
```

## Key Design Principles

1. **Type Safety**: Use dataclasses for all state management
2. **Observability**: Append-only trace logs for debugging
3. **Structured Artifacts**: Manifest-based artifact management
4. **Isolation**: Each run is completely isolated in its own directory
5. **Idempotency**: State can be saved and restored at any point
6. **Debuggability**: view.html for easy result inspection

## Extension Points

1. **Custom Generators**: Implement generator interface
2. **Custom Evaluators**: Implement evaluator interface
3. **Additional Artifacts**: Use ArtifactsManager.save_file()
4. **Custom Trace Events**: Add new TraceEventType values
5. **Multiple Files**: Extend generator to return multiple files

## Testing

```bash
# Test lifecycle components
python test_lifecycle.py

# Test full run
python -m orchestrator.main "Test task"

# View results
open runs/<run_id>/artifacts/view.html
```

## Production Considerations

1. **API Keys**: Secure storage of GOOGLE_AI_STUDIO_API_KEY
2. **Resource Limits**: Set max_iterations, timeouts
3. **Cleanup**: Periodically clean old runs/
4. **Monitoring**: Parse trace.jsonl for metrics
5. **Scaling**: Run multiple orchestrators in parallel
6. **Persistence**: Consider database for run metadata
