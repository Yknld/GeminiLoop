# Path Configuration Quick Reference

## 🚀 Quick Start

```python
from orchestrator.paths import get_path_config
from orchestrator.preview_server import get_preview_server

# Get canonical paths (single source of truth)
path_config = get_path_config()

# Start preview server (replaces file:// URLs)
preview_server = get_preview_server(
    serve_dir=path_config.project_root,
    host=path_config.preview_host,
    port=path_config.preview_port
)

# Use HTTP URLs (never file://)
preview_url = preview_server.get_file_url("index.html")
# → http://127.0.0.1:8000/index.html
```

## 📁 Canonical Directories

| Directory | Path | Purpose | Access |
|-----------|------|---------|--------|
| `WORKSPACE_ROOT` | Auto-detected | Base directory | Read/Write |
| `PROJECT_ROOT` | `${WORKSPACE_ROOT}/project` | Agent workspace | Validated R/W |
| `SITE_ROOT` | `${WORKSPACE_ROOT}/site` | Evaluator compat | Read/Write |

## 🔐 Security

```python
# ✅ Safe path operations
safe_file = path_config.safe_path_join("index.html")

# ✅ Validate before writing
if path_config.validate_path_in_project(user_path):
    user_path.write_text("content")

# ❌ Blocked - raises ValueError
bad_path = path_config.safe_path_join("../../../etc/passwd")
```

## 🌐 Preview Server

```python
# Start server (automatic in main.py)
preview_server = get_preview_server(serve_dir=PROJECT_ROOT)

# Get URLs
base_url = preview_server.url  # http://127.0.0.1:8000/
file_url = preview_server.get_file_url("page.html")

# Check status
if preview_server.is_running:
    print(f"Serving from: {preview_server.url}")

# Stop server (automatic cleanup)
stop_preview_server()
```

## ⚙️ Environment Variables

```bash
# Override workspace root
export WORKSPACE_ROOT=/custom/workspace

# Preview server config
export PREVIEW_HOST=0.0.0.0     # External access
export PREVIEW_PORT=8080        # Custom port
```

## 📊 Startup Logging

Every run automatically logs:
- ✅ Directory paths (WORKSPACE_ROOT, PROJECT_ROOT, SITE_ROOT)
- ✅ Preview server URL
- ✅ Current working directory
- ✅ Directory contents

## 🔄 Migration

### Before (❌)
```python
workspace = Path("/workspace")
url = f"file://{workspace}/index.html"
```

### After (✅)
```python
path_config = get_path_config()
preview_server = get_preview_server(serve_dir=path_config.project_root)
url = preview_server.get_file_url("index.html")
```

## 🧪 Testing

```bash
# Run all tests
python3 test_paths.py

# Check path config
python3 -c "from orchestrator.paths import get_path_config; \
            get_path_config().log_startup_info()"

# Verify preview server
curl http://127.0.0.1:8000/
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "file:// blocked" | Use HTTP preview server (automatic) |
| "Path outside PROJECT_ROOT" | Use `safe_path_join()` |
| "Port 8000 in use" | Set `PREVIEW_PORT=8001` |
| "Server not accessible" | Set `PREVIEW_HOST=0.0.0.0` |

## 📚 Full Documentation

- **Quick Reference**: This file
- **Complete Guide**: [RUNPOD_PATH_CONTRACT.md](RUNPOD_PATH_CONTRACT.md)
- **Architecture**: [PATH_ARCHITECTURE.md](PATH_ARCHITECTURE.md)
- **Implementation**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## 🎯 Key Principles

1. **Single Source of Truth**: All paths from `paths.py` module
2. **HTTP Only**: Never use `file://` URLs
3. **Validated Operations**: All writes validated via `safe_path_join()`
4. **Comprehensive Logging**: Full path visibility on startup
5. **Security First**: Path traversal protection built-in

---

**Status**: Production Ready ✅  
**Last Updated**: 2026-01-16
