# RunPod/OpenHands Path Source of Truth

This document defines the **single source of truth** for all file paths and directory operations in GeminiLoop when deployed on RunPod with OpenHands.

## Problem Statement

Prior to this implementation, the system suffered from:

- **Inconsistent file paths**: Mixed usage of `/workspace`, `/site`, and project directories
- **Blocked file:// navigation**: Browser automation failed due to file:// protocol restrictions
- **No path validation**: Risk of writing outside intended directories
- **Difficult debugging**: No centralized path logging or visibility

## Solution Overview

All path operations are now centralized in the `paths.py` module, which provides:

1. **Canonical directory definitions**
2. **Path validation and guardrails**
3. **HTTP preview server (replaces file:// URLs)**
4. **Comprehensive startup logging**

## Canonical Directories

### WORKSPACE_ROOT

**Definition**: The OpenHands runtime workspace directory.

**Detection Priority**:
1. `WORKSPACE_ROOT` environment variable (explicit override)
2. OpenHands standard directories (`/workspace`, `/root/workspace`)
3. Current working directory (fallback)

**Usage**: Base directory for all run operations.

```python
from orchestrator.paths import get_path_config

path_config = get_path_config()
print(path_config.workspace_root)  # e.g., /workspace
```

### PROJECT_ROOT

**Definition**: `${WORKSPACE_ROOT}/project` - where the agent reads/writes files.

**Purpose**: 
- All code generation output goes here
- OpenHands agent operates within this directory
- Preview server serves from this directory

**Guardrails**: 
- All write operations validated to be within PROJECT_ROOT
- `safe_path_join()` prevents path traversal attacks
- `validate_path_in_project()` enforces boundaries

```python
# Safe path operations
safe_file = path_config.safe_path_join("index.html")  # ✅ Allowed
# unsafe_file = path_config.safe_path_join("../etc/passwd")  # ❌ Raises ValueError
```

### SITE_ROOT

**Definition**: `${WORKSPACE_ROOT}/site` - compatibility directory for evaluator.

**Purpose**:
- Used if evaluator explicitly requires `/site/index.html`
- Files copied from PROJECT_ROOT to SITE_ROOT after generation
- Maintained for backward compatibility only

**Note**: In the future, this may be deprecated in favor of PROJECT_ROOT only.

## HTTP Preview Server

### Overview

Replaces **all** `file://` URLs with HTTP serving to fix navigation issues.

### Implementation

```python
from orchestrator.preview_server import get_preview_server

# Start server (happens automatically in main.py)
preview_server = get_preview_server(
    serve_dir=path_config.project_root,
    host="127.0.0.1",  # or "0.0.0.0" for external access
    port=8000
)

# Get URLs
preview_url = preview_server.url  # http://127.0.0.1:8000/
file_url = preview_server.get_file_url("index.html")  # http://127.0.0.1:8000/index.html
```

### Configuration

Environment variables:
- `PREVIEW_HOST`: Server host (default: `127.0.0.1`)
- `PREVIEW_PORT`: Server port (default: `8000`)

### Lifecycle

- Started: At beginning of `run_loop()`
- Serves: From `PROJECT_ROOT`
- Stopped: Automatically in `finally` block
- Thread: Background daemon thread (non-blocking)

## Startup Logging

On every run, the system logs comprehensive path information:

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
   📄 index.html
   📄 styles.css

📂 Contents of SITE_ROOT (/workspace/site):
   📄 index.html

======================================================================
```

This logging happens automatically via `path_config.log_startup_info()`.

## Usage Examples

### Basic Setup

```python
from orchestrator.paths import get_path_config
from orchestrator.preview_server import get_preview_server

# Get path configuration (singleton)
path_config = get_path_config()

# Start preview server
preview_server = get_preview_server(
    serve_dir=path_config.project_root,
    host=path_config.preview_host,
    port=path_config.preview_port
)

# Use HTTP URL (not file://)
preview_url = preview_server.get_file_url("index.html")
print(f"Preview at: {preview_url}")
```

### Safe File Operations

```python
# ✅ Safe - stays within PROJECT_ROOT
output_file = path_config.safe_path_join("output", "result.html")
output_file.write_text("<html>...</html>")

# ✅ Validate before writing
user_path = Path(user_input)
if path_config.validate_path_in_project(user_path):
    user_path.write_text("safe content")
else:
    raise ValueError("Path outside PROJECT_ROOT")

# ❌ This raises ValueError
try:
    bad_path = path_config.safe_path_join("../../../etc/passwd")
except ValueError as e:
    print(f"Blocked: {e}")
```

### OpenHands Integration

```python
from orchestrator.openhands_client import get_openhands_client

# OpenHands workspace should always be PROJECT_ROOT
openhands = get_openhands_client()
result = openhands.generate_code(
    task="Create a landing page",
    workspace_path=str(path_config.project_root),  # ✅ Use PROJECT_ROOT
    detailed_requirements={...}
)

# Files are generated in PROJECT_ROOT
for filename in result["files_generated"]:
    file_path = path_config.project_root / filename
    assert file_path.exists()
```

### Evaluator Integration

```python
from orchestrator.evaluator import GeminiEvaluator

evaluator = GeminiEvaluator()

# Use HTTP URL (not file://)
evaluation = await evaluator.evaluate(
    url=preview_server.get_file_url("index.html"),  # ✅ HTTP URL
    mcp_client=mcp,
    task=task,
    screenshots_dir=screenshots_dir
)

# ❌ Never use file:// URLs
# bad_url = f"file://{path_config.project_root}/index.html"  # Will fail on RunPod
```

## File Copy Strategy

When files need to be in multiple locations (workspace, site, project):

```python
# After OpenHands generates code in workspace_dir
for filename in files_generated:
    src = workspace_dir / filename
    
    if src.exists():
        # 1. Copy to SITE_ROOT (compatibility)
        dst_site = site_dir / filename
        dst_site.parent.mkdir(parents=True, exist_ok=True)
        dst_site.write_text(src.read_text())
        
        # 2. Copy to PROJECT_ROOT (preview server)
        dst_project = path_config.safe_path_join(filename)
        dst_project.parent.mkdir(parents=True, exist_ok=True)
        dst_project.write_text(src.read_text())
```

## Environment Variables

Configure paths via environment:

```bash
# Override workspace root
export WORKSPACE_ROOT=/custom/workspace

# Preview server configuration
export PREVIEW_HOST=0.0.0.0  # Allow external access
export PREVIEW_PORT=8080     # Custom port

# Run
python -m orchestrator.main "Create a quiz app"
```

## Testing

### Local Development

```bash
# Use current directory as workspace
cd /path/to/project
python -m orchestrator.main "task"

# Paths will be:
# WORKSPACE_ROOT: /path/to/project
# PROJECT_ROOT: /path/to/project/project
# Preview: http://127.0.0.1:8000/
```

### RunPod Deployment

```bash
# RunPod automatically sets up /workspace
docker run -e WORKSPACE_ROOT=/workspace \
           -e GOOGLE_AI_STUDIO_API_KEY=... \
           gemini-loop

# Paths will be:
# WORKSPACE_ROOT: /workspace
# PROJECT_ROOT: /workspace/project
# Preview: http://127.0.0.1:8000/
```

## Debugging

### Check Path Configuration

```python
from orchestrator.paths import get_path_config

config = get_path_config()
config.log_startup_info()  # Prints comprehensive path info
```

### Verify Preview Server

```bash
# Check if server is running
curl http://127.0.0.1:8000/

# Check specific file
curl http://127.0.0.1:8000/index.html
```

### Validate File Operations

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# All path operations will be logged
path_config = get_path_config()
safe_file = path_config.safe_path_join("test.html")
```

## Migration Guide

If you have existing code using file:// URLs or hardcoded paths:

### Before

```python
# ❌ Hardcoded paths
workspace = Path("/workspace")
site_dir = Path("/site")
preview_url = f"file://{site_dir}/index.html"
```

### After

```python
# ✅ Use paths module
from orchestrator.paths import get_path_config
from orchestrator.preview_server import get_preview_server

path_config = get_path_config()
preview_server = get_preview_server(
    serve_dir=path_config.project_root,
    host=path_config.preview_host,
    port=path_config.preview_port
)

preview_url = preview_server.get_file_url("index.html")
```

## Security Considerations

### Path Validation

All file operations must be validated:

```python
# Guardrails prevent writing outside PROJECT_ROOT
try:
    # This will fail if path escapes PROJECT_ROOT
    safe_path = path_config.safe_path_join(user_input)
except ValueError:
    # Handle invalid path
    pass
```

### Preview Server Security

- Serves only from PROJECT_ROOT
- No directory traversal allowed
- CORS headers for browser compatibility
- Local-only by default (127.0.0.1)

## Troubleshooting

### "file:// navigation blocked"

**Solution**: Use HTTP preview server instead.

```python
# ❌ Don't use
url = f"file://{path}/index.html"

# ✅ Use instead
url = preview_server.get_file_url("index.html")
```

### "Path outside PROJECT_ROOT"

**Solution**: Use `safe_path_join()` for all path operations.

```python
# ❌ Don't use
path = project_root / user_input

# ✅ Use instead
path = path_config.safe_path_join(user_input)
```

### "Port 8000 already in use"

**Solution**: Change preview port.

```bash
export PREVIEW_PORT=8001
```

Or configure in code:

```python
path_config = get_path_config()
path_config.preview_port = 8001
```

### Preview server not accessible

**Solution**: Bind to 0.0.0.0 for external access.

```bash
export PREVIEW_HOST=0.0.0.0
```

## Future Improvements

1. **Deprecate SITE_ROOT**: Move entirely to PROJECT_ROOT-only workflow
2. **Add path caching**: Cache resolved paths for performance
3. **Add path metrics**: Track file operations for observability
4. **Add path snapshots**: Capture directory state at each phase
5. **Add path validation in OpenHands**: Ensure agent stays in bounds

## References

- `orchestrator/paths.py` - Path configuration module
- `orchestrator/preview_server.py` - HTTP preview server
- `orchestrator/main.py` - Integration in orchestration loop
- `orchestrator/openhands_client.py` - OpenHands path handling
- `orchestrator/evaluator.py` - Evaluator URL handling

## Contact

For issues or questions about path handling, see:
- GitHub Issues: [GeminiLoop issues](https://github.com/yourusername/GeminiLoop/issues)
- Documentation: [README.md](README.md)

---

**Last Updated**: 2026-01-16  
**Version**: 1.0.0
