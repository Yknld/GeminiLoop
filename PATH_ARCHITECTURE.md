# GeminiLoop Path Architecture

## Directory Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                        WORKSPACE_ROOT                           │
│                   (auto-detected on startup)                    │
│                                                                 │
│  Examples:                                                      │
│  - RunPod: /workspace                                           │
│  - Local: /Users/you/GeminiLoop                                │
│  - Docker: /app/workspace                                       │
│  - Custom: $WORKSPACE_ROOT env var                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
      ┌─────────────┐  ┌────────────┐  ┌───────────┐
      │   project/  │  │   site/    │  │   runs/   │
      │             │  │            │  │           │
      │ PROJECT_ROOT│  │  SITE_ROOT │  │ Run Data  │
      └─────────────┘  └────────────┘  └───────────┘
```

## Component Breakdown

### WORKSPACE_ROOT
```
Purpose:     Base directory for all operations
Detection:   Automatic (see priority below)
Access:      path_config.workspace_root
Permissions: Read/Write
Used By:     All components

Detection Priority:
1. WORKSPACE_ROOT env var (explicit override)
2. /workspace (RunPod standard)
3. /root/workspace (alternative)
4. Current working directory (fallback)
```

### PROJECT_ROOT
```
Path:        ${WORKSPACE_ROOT}/project
Purpose:     Agent's working directory
Access:      path_config.project_root
Permissions: Read/Write (with validation)
Used By:     
  - OpenHands agent (reads/writes here)
  - Preview server (serves from here)
  - Code generator (outputs here)
  
Security:
  ✅ All write operations validated
  ✅ Path traversal blocked
  ✅ safe_path_join() enforces boundaries
  
Example Contents:
  PROJECT_ROOT/
  ├── index.html
  ├── styles.css
  ├── script.js
  └── assets/
      └── logo.png
```

### SITE_ROOT
```
Path:        ${WORKSPACE_ROOT}/site
Purpose:     Compatibility directory (evaluator)
Access:      path_config.site_root
Permissions: Read/Write
Used By:     Evaluator (if required)
Status:      May be deprecated in future

Note: Files are copied from PROJECT_ROOT to SITE_ROOT
      after generation for evaluator compatibility.

Example Contents:
  SITE_ROOT/
  └── index.html  (copy from PROJECT_ROOT)
```

### Runs Directory
```
Path:        ${WORKSPACE_ROOT}/runs
Purpose:     Store run artifacts and history
Structure:   
  runs/
  └── {run_id}/
      ├── workspace/    (OpenHands workspace copy)
      ├── artifacts/    (logs, screenshots, reports)
      │   ├── screenshots/
      │   ├── diffs/
      │   ├── trace.jsonl
      │   └── manifest.json
      └── site/         (final output)
```

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  1. USER SUBMITS TASK                                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. PATH CONFIGURATION                                           │
│                                                                  │
│  path_config = get_path_config()                                 │
│  ✅ WORKSPACE_ROOT detected                                      │
│  ✅ PROJECT_ROOT created                                         │
│  ✅ SITE_ROOT created                                            │
│  ✅ Startup logging displayed                                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. PREVIEW SERVER STARTUP                                       │
│                                                                  │
│  preview_server = get_preview_server(                            │
│      serve_dir=path_config.project_root,                         │
│      host="127.0.0.1",                                           │
│      port=8000                                                   │
│  )                                                               │
│  ✅ HTTP server started                                          │
│  ✅ Serving from PROJECT_ROOT                                    │
│  ✅ URL: http://127.0.0.1:8000/                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  4. CODE GENERATION (OpenHands)                                  │
│                                                                  │
│  openhands.generate_code(                                        │
│      workspace_path=run_state.workspace_dir  ← Temp workspace    │
│  )                                                               │
│  ✅ Files generated in workspace_dir                             │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  5. FILE COPYING                                                 │
│                                                                  │
│  for file in generated_files:                                    │
│      workspace_dir/file  ────────┐                               │
│                                  │                               │
│                                  ├──► SITE_ROOT/file              │
│                                  │                               │
│                                  └──► PROJECT_ROOT/file           │
│                                                                  │
│  ✅ Files in PROJECT_ROOT (for preview server)                   │
│  ✅ Files in SITE_ROOT (for evaluator compat)                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  6. EVALUATION                                                   │
│                                                                  │
│  preview_url = preview_server.get_file_url("index.html")         │
│  # → http://127.0.0.1:8000/index.html                            │
│                                                                  │
│  evaluator.evaluate(                                             │
│      url=preview_url  ← HTTP URL (not file://)                   │
│  )                                                               │
│  ✅ Browser navigates to HTTP URL                                │
│  ✅ Screenshots saved to artifacts/                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  7. PATCH APPLICATION (if needed)                                │
│                                                                  │
│  openhands.apply_patch_plan(                                     │
│      workspace_path=run_state.workspace_dir                      │
│  )                                                               │
│  ✅ Files modified in workspace_dir                              │
│  ✅ Files copied to PROJECT_ROOT + SITE_ROOT                     │
│  ✅ Preview server serves updated files                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  8. CLEANUP                                                      │
│                                                                  │
│  stop_preview_server()                                           │
│  ✅ HTTP server stopped                                          │
│  ✅ All artifacts saved                                          │
└──────────────────────────────────────────────────────────────────┘
```

## URL Strategy

### ❌ OLD (Blocked on RunPod)
```python
# file:// URLs fail in Docker/RunPod
url = f"file://{site_dir}/index.html"
# → file:///workspace/site/index.html
# ❌ BLOCKED by browser security
```

### ✅ NEW (HTTP Preview)
```python
# HTTP URLs work everywhere
preview_server = get_preview_server(serve_dir=PROJECT_ROOT)
url = preview_server.get_file_url("index.html")
# → http://127.0.0.1:8000/index.html
# ✅ WORKS in all contexts
```

## Security Model

```
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY BOUNDARIES                        │
└─────────────────────────────────────────────────────────────────┘

                   ┌─────────────────────────┐
                   │   WORKSPACE_ROOT        │
                   │   (unrestricted)        │
                   └───────────┬─────────────┘
                               │
                   ┌───────────┼───────────┐
                   │           │           │
          ┌────────▼──────┐    │    ┌──────▼──────┐
          │  PROJECT_ROOT │    │    │  SITE_ROOT  │
          │  ┏━━━━━━━━━━┓ │    │    │ (read-only) │
          │  ┃ SECURED  ┃ │    │    └─────────────┘
          │  ┃ BOUNDARY ┃ │    │
          │  ┗━━━━━━━━━━┛ │    │
          │               │    │
          │  ✅ Validated │    │
          │  ✅ No ../..  │    │
          │  ✅ Logged    │    │
          └───────────────┘    │
                               │
                   ┌───────────▼────────────┐
                   │     Other Dirs         │
                   │   (not accessible)     │
                   │                        │
                   │  ❌ /etc/              │
                   │  ❌ /usr/              │
                   │  ❌ /root/             │
                   └────────────────────────┘

Path Validation Functions:
  ✅ validate_path_in_project(path)
  ✅ safe_path_join(*parts)
  ✅ Path.resolve() + is_relative_to()
```

## Environment Configuration

```bash
# Override workspace root
export WORKSPACE_ROOT=/custom/workspace

# Preview server config
export PREVIEW_HOST=0.0.0.0     # Allow external access
export PREVIEW_PORT=8080        # Custom port

# Example: RunPod deployment
docker run \
  -e WORKSPACE_ROOT=/workspace \
  -e PREVIEW_HOST=0.0.0.0 \
  -e PREVIEW_PORT=8000 \
  -e GOOGLE_AI_STUDIO_API_KEY=... \
  -p 8000:8000 \
  gemini-loop:latest
```

## Observability

### Startup Logging
```
======================================================================
PATH CONFIGURATION - SINGLE SOURCE OF TRUTH
======================================================================

📁 Directory Configuration:
   WORKSPACE_ROOT: /workspace
   PROJECT_ROOT: /workspace/project
   SITE_ROOT: /workspace/site

🌐 Preview Server:
   Host: 127.0.0.1
   Port: 8000
   URL: http://127.0.0.1:8000/

📍 Current Working Directory:
   pwd: /app

📂 Contents of WORKSPACE_ROOT (/workspace):
   📁 project
   📁 site
   📁 runs

📂 Contents of PROJECT_ROOT (/workspace/project):
   (empty)

📂 Contents of SITE_ROOT (/workspace/site):
   (empty)

======================================================================
```

### Runtime Logging
```
✅ Path detection works
✅ Directories ensured
✅ Preview server started on http://127.0.0.1:8000/
   Serving from: /workspace/project
✅ OpenHands workspace: /workspace/runs/20260116_abc123/workspace
✅ Files generated: ['index.html', 'styles.css']
✅ Copied index.html to preview server
✅ Evaluation complete
✅ Preview server stopped
```

## Code Examples

### Basic Setup
```python
from orchestrator.paths import get_path_config
from orchestrator.preview_server import get_preview_server

# Get path config (singleton)
path_config = get_path_config()

# Start preview server
preview_server = get_preview_server(
    serve_dir=path_config.project_root,
    host=path_config.preview_host,
    port=path_config.preview_port
)

# Get URLs
base_url = preview_server.url  # http://127.0.0.1:8000/
file_url = preview_server.get_file_url("index.html")
```

### Safe File Operations
```python
# ✅ Safe - validated
output = path_config.safe_path_join("output.html")
output.write_text("<html>...</html>")

# ❌ Blocked - raises ValueError
try:
    bad = path_config.safe_path_join("../../etc/passwd")
except ValueError as e:
    print(f"Security error: {e}")
```

### Integration with OpenHands
```python
# Generate code in workspace
result = openhands.generate_code(
    task="Create a landing page",
    workspace_path=str(workspace_dir),
    detailed_requirements=requirements
)

# Copy to PROJECT_ROOT for preview
for filename in result["files_generated"]:
    src = workspace_dir / filename
    dst = path_config.safe_path_join(filename)
    dst.write_text(src.read_text())

# Serve via HTTP
url = preview_server.get_file_url("index.html")
```

## Troubleshooting

### Problem: "file:// navigation blocked"
**Solution**: System now uses HTTP preview server automatically.
No action needed.

### Problem: "Path outside PROJECT_ROOT"
**Solution**: Use `safe_path_join()` instead of direct path operations.

```python
# ❌ Don't do this
path = project_root / user_input

# ✅ Do this instead
path = path_config.safe_path_join(user_input)
```

### Problem: "Port 8000 already in use"
**Solution**: Change port via environment variable.

```bash
export PREVIEW_PORT=8001
```

### Problem: "Preview server not accessible"
**Solution**: Bind to 0.0.0.0 for external access.

```bash
export PREVIEW_HOST=0.0.0.0
```

## Future Roadmap

1. **Phase 1 (Complete)**: ✅
   - Centralized path configuration
   - HTTP preview server
   - Security guardrails
   - Comprehensive logging

2. **Phase 2 (Future)**:
   - Deprecate SITE_ROOT
   - Direct PROJECT_ROOT-only workflow
   - Enhanced path metrics

3. **Phase 3 (Future)**:
   - Path caching for performance
   - Directory snapshots at each phase
   - Advanced security policies

## References

- Implementation: [orchestrator/paths.py](orchestrator/paths.py)
- Preview Server: [orchestrator/preview_server.py](orchestrator/preview_server.py)
- Documentation: [RUNPOD_PATH_CONTRACT.md](RUNPOD_PATH_CONTRACT.md)
- Summary: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Tests: [test_paths.py](test_paths.py)

---

**Last Updated**: 2026-01-16  
**Status**: Production Ready ✅
