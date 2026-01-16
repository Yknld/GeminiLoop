# Template Bootstrap Guide

## Overview

**Template Bootstrap** ensures each OpenHands job starts from a clean, consistent Git repository template. This eliminates path confusion and provides a standardized project structure.

## Why Template Bootstrap?

**Before** (without template):
- ❌ Inconsistent file paths across runs
- ❌ OpenHands creates files from scratch (slower)
- ❌ No standard project structure
- ❌ Difficult to enforce conventions

**After** (with template):
- ✅ Every run starts from the same clean template
- ✅ Consistent file paths and structure
- ✅ Pre-configured build tools, dependencies
- ✅ Faster initialization (no file creation from scratch)
- ✅ Easy to enforce project standards

## Configuration

### Required Environment Variables

```bash
# Git repository URL (required to enable template bootstrap)
TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
```

### Optional Environment Variables

```bash
# Git ref to checkout (branch, tag, or commit SHA)
# Default: main
TEMPLATE_REF=main

# Project directory name (relative to WORKSPACE_ROOT)
# Default: project
PROJECT_DIR_NAME=project

# Run template init script if present (init.sh, bootstrap.sh, setup.sh)
# Default: false
RUN_TEMPLATE_INIT=false

# Copy output to SITE_ROOT for evaluator compatibility
# Default: false
PUBLISH_TO_SITE=false
```

## Quick Start

### 1. Basic Template Bootstrap

```bash
# Set template repository
export TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git

# Run GeminiLoop
python -m orchestrator.main "Create a quiz app"
```

**What happens:**
1. Template repository cloned to `${WORKSPACE_ROOT}/project`
2. Files ready for OpenHands to modify
3. Preview server serves from `PROJECT_ROOT`

### 2. Use Specific Branch/Tag

```bash
# Clone from specific branch
export TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
export TEMPLATE_REF=feature/new-layout

# Or use a specific tag
export TEMPLATE_REF=v1.2.0

# Or use a commit SHA
export TEMPLATE_REF=abc123def456

python -m orchestrator.main "Build a dashboard"
```

### 3. Run Template Init Script

If your template includes an `init.sh` script:

```bash
export TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
export RUN_TEMPLATE_INIT=true

python -m orchestrator.main "Create a landing page"
```

**Init script examples:**
- Install npm dependencies: `npm install`
- Setup environment: `cp .env.example .env`
- Generate assets: `npm run build-assets`

### 4. Custom Project Directory Name

```bash
export TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
export PROJECT_DIR_NAME=webapp

python -m orchestrator.main "Build an app"
# Project will be at ${WORKSPACE_ROOT}/webapp
```

## Creating a Template Repository

### Minimal Template Structure

```
my-webapp-template/
├── index.html           # Entry point
├── styles.css           # Styles
├── script.js            # JavaScript
├── README.md            # Template documentation
└── .gitignore           # Git ignore rules
```

### Advanced Template Structure

```
my-webapp-template/
├── index.html
├── styles/
│   ├── main.css
│   └── components.css
├── scripts/
│   └── app.js
├── assets/
│   └── logo.png
├── init.sh              # Optional init script
├── package.json         # npm dependencies (optional)
├── README.md
└── .gitignore
```

### Example init.sh

```bash
#!/bin/bash
set -e

echo "🔧 Initializing template..."

# Install dependencies if package.json exists
if [ -f "package.json" ]; then
    echo "📦 Installing npm dependencies..."
    npm install --silent
fi

# Setup environment
if [ -f ".env.example" ]; then
    echo "⚙️  Setting up environment..."
    cp .env.example .env
fi

# Build assets
if [ -f "package.json" ] && grep -q "build" package.json; then
    echo "🏗️  Building assets..."
    npm run build
fi

echo "✅ Template initialized successfully"
```

Make it executable:
```bash
chmod +x init.sh
```

## Bootstrap Process

The bootstrap process runs automatically at the start of each OpenHands job:

```
1. Determine WORKSPACE_ROOT
   ↓
2. Clean existing ${WORKSPACE_ROOT}/${PROJECT_DIR_NAME}
   ↓
3. git clone --depth 1 ${TEMPLATE_REPO_URL} → PROJECT_ROOT
   ↓
4. git checkout ${TEMPLATE_REF} (if not main/master)
   ↓
5. Run init script (if RUN_TEMPLATE_INIT=true and script exists)
   ↓
6. Log project structure
   ↓
7. Start preview server from PROJECT_ROOT
   ↓
8. OpenHands operates on PROJECT_ROOT files
```

## RunPod Deployment

### Docker Run

```bash
docker run \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  -e TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git \
  -e TEMPLATE_REF=main \
  -e RUN_TEMPLATE_INIT=false \
  -p 8000:8000 \
  -p 8080:8080 \
  gemini-loop:latest
```

### RunPod Template

In RunPod console, add environment variables:

```
GOOGLE_AI_STUDIO_API_KEY=your_key_here
TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
TEMPLATE_REF=main
RUN_TEMPLATE_INIT=false
PUBLISH_TO_SITE=false
```

### Docker Compose

```yaml
version: '3.8'

services:
  gemini-loop:
    image: gemini-loop:latest
    ports:
      - "8000:8000"
      - "8080:8080"
    environment:
      - GOOGLE_AI_STUDIO_API_KEY=${GOOGLE_AI_STUDIO_API_KEY}
      - TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
      - TEMPLATE_REF=main
      - PROJECT_DIR_NAME=project
      - RUN_TEMPLATE_INIT=false
      - PUBLISH_TO_SITE=false
    volumes:
      - ./runs:/workspace/runs
```

## Security Considerations

### Git Authentication

**Public repositories**: No authentication needed.

**Private repositories**: Use Git credentials or SSH keys.

#### Option 1: HTTPS with Token

```bash
# GitHub Personal Access Token
export TEMPLATE_REPO_URL=https://TOKEN@github.com/your-org/private-template.git
```

#### Option 2: SSH Key

```bash
# Use SSH URL
export TEMPLATE_REPO_URL=git@github.com:your-org/private-template.git

# Mount SSH key in Docker
docker run \
  -v ~/.ssh:/root/.ssh:ro \
  -e TEMPLATE_REPO_URL=git@github.com:your-org/private-template.git \
  gemini-loop:latest
```

### Path Security

Template bootstrap enforces security boundaries:

```python
# ✅ Validated - stays within PROJECT_ROOT
from orchestrator.paths import get_path_config
path_config = get_path_config()
safe_path = path_config.safe_path_join("component.html")

# ❌ Blocked - raises ValueError
bad_path = path_config.safe_path_join("../../etc/passwd")
```

### Init Script Safety

- Init scripts run with project directory permissions
- Timeout after 5 minutes to prevent hangs
- stdout/stderr captured for debugging
- Failure logged but does not abort run

## Troubleshooting

### Problem: "git: command not found"

**Solution**: Ensure git is installed in container.

```dockerfile
RUN apt-get update && apt-get install -y git
```

### Problem: Clone fails with authentication error

**Solution**: Check repository URL and credentials.

```bash
# Test clone manually
git clone ${TEMPLATE_REPO_URL} /tmp/test-clone
```

For private repos, use token or SSH key (see Security section).

### Problem: Clone timeout after 5 minutes

**Solution**: Repository is too large. Consider:
1. Reducing repository size (remove large assets)
2. Using shallow clone (already enabled: `--depth 1`)
3. Increasing timeout in `bootstrap.py`

### Problem: Init script fails

**Check logs:**
```bash
# Bootstrap logs show init script output
grep "init script" /workspace/runs/*/artifacts/trace.jsonl
```

**Common issues:**
- Missing dependencies (npm, python, etc.)
- Incorrect script permissions (use `chmod +x init.sh`)
- Script expects environment variables

**Solution**: Fix script or disable with `RUN_TEMPLATE_INIT=false`

### Problem: Wrong branch checked out

**Solution**: Verify `TEMPLATE_REF` matches branch/tag name.

```bash
# List available branches
git ls-remote --heads ${TEMPLATE_REPO_URL}

# List available tags
git ls-remote --tags ${TEMPLATE_REPO_URL}
```

## Integration with OpenHands

OpenHands operates on the bootstrapped template:

```python
# Bootstrap creates clean template
bootstrap_result = bootstrap_from_template(workspace_root)

# OpenHands modifies template files
openhands.generate_code(
    task="Add a contact form",
    workspace_path=str(project_root),
    detailed_requirements=requirements
)

# Preview server serves modified files
preview_url = preview_server.get_file_url("index.html")
```

## Publishing to SITE_ROOT

If your evaluator requires files in `SITE_ROOT`:

```bash
export PUBLISH_TO_SITE=true
```

**What happens:**
1. OpenHands modifies files in `PROJECT_ROOT`
2. After each iteration, files copied to `SITE_ROOT`
3. Evaluator can access files at both locations

**Recommended**: Update evaluator to use `PROJECT_ROOT` directly.

## Example Templates

### 1. Minimal HTML Template

```bash
# Clone minimal template
export TEMPLATE_REPO_URL=https://github.com/gemini-loop/template-html-minimal.git
```

**Contents:**
- `index.html` - Basic HTML5 structure
- `styles.css` - Reset styles
- `script.js` - Empty JS file

### 2. Bootstrap CSS Template

```bash
# Clone Bootstrap template
export TEMPLATE_REPO_URL=https://github.com/gemini-loop/template-bootstrap.git
export RUN_TEMPLATE_INIT=true  # Installs Bootstrap via npm
```

**Contents:**
- `index.html` - Bootstrap grid structure
- `package.json` - Bootstrap dependencies
- `init.sh` - Runs `npm install`

### 3. React Template

```bash
# Clone React template
export TEMPLATE_REPO_URL=https://github.com/gemini-loop/template-react.git
export TEMPLATE_REF=v18
export RUN_TEMPLATE_INIT=true  # Installs dependencies and builds
```

**Contents:**
- `src/` - React components
- `public/` - Static assets
- `package.json` - React dependencies
- `init.sh` - Runs `npm install && npm run build`

## Monitoring

### Bootstrap Logs

Bootstrap process logs comprehensively:

```
======================================================================
TEMPLATE BOOTSTRAP
======================================================================
📦 Template: https://github.com/your-org/webapp-template.git
🔀 Ref: main
📁 Target: /workspace/project
======================================================================

🧹 Cleaning project directory...
   Path: /workspace/project
   Removing 42 files...
   ✅ Cleaned successfully

📥 Cloning template repository...
   URL: https://github.com/your-org/webapp-template.git
   Target: /workspace/project
   Command: git clone --depth 1 --single-branch ...
   ✅ Clone successful

🔀 Ref: main (default branch, skipping checkout)

📂 Project structure:
   Files: 15
   Directories: 3

   Top-level items:
   📄 index.html
   📄 styles.css
   📄 script.js
   📁 assets
   📄 README.md

======================================================================
✅ TEMPLATE BOOTSTRAP COMPLETE
======================================================================
```

### Trace Events

Bootstrap results saved to trace:

```jsonl
{"event": "info", "message": "Template bootstrap successful", "data": {...}}
```

### Manifest

Bootstrap metadata in manifest:

```json
{
  "github_enabled": true,
  "github_repo": "https://github.com/your-org/webapp-template.git",
  "github_branch": "main"
}
```

## Best Practices

1. **Keep templates minimal**: Only include essential files
2. **Use shallow clones**: Enabled by default for speed
3. **Version your templates**: Use tags for stable versions
4. **Test init scripts**: Ensure they run quickly (<1 minute)
5. **Document templates**: Include README.md with usage
6. **Separate concerns**: Data vs. structure vs. styling
7. **Use .gitignore**: Exclude node_modules, build artifacts
8. **Validate templates**: Test bootstrap process locally

## API Reference

### TemplateConfig

```python
from orchestrator.bootstrap import TemplateConfig

config = TemplateConfig(
    repo_url="https://github.com/org/template.git",
    ref="main",
    project_dir_name="project",
    run_init=False,
    publish_to_site=False
)

# Or from environment
config = TemplateConfig.from_env()

# Check if enabled
if config.is_enabled():
    print("Template bootstrap enabled")
```

### TemplateBootstrap

```python
from orchestrator.bootstrap import TemplateBootstrap
from pathlib import Path

bootstrap = TemplateBootstrap(
    workspace_root=Path("/workspace"),
    config=config
)

# Run bootstrap
result = bootstrap.bootstrap()

# Publish to site (optional)
publish_result = bootstrap.publish_to_site(
    site_root=Path("/workspace/site")
)
```

### bootstrap_from_template()

```python
from orchestrator.bootstrap import bootstrap_from_template
from pathlib import Path

# Bootstrap with default config (from env)
result = bootstrap_from_template(
    workspace_root=Path("/workspace")
)

# Or with custom config
result = bootstrap_from_template(
    workspace_root=Path("/workspace"),
    config=custom_config
)

# Check result
if result["success"]:
    print(f"Files: {result['files_count']}")
else:
    print(f"Error: {result['error']}")
```

## Migration from GitHub Integration

Old approach (GitHub clone):
```bash
export GITHUB_TOKEN=ghp_...
export GITHUB_REPO=your-org/repo
```

New approach (Template bootstrap):
```bash
export TEMPLATE_REPO_URL=https://github.com/your-org/webapp-template.git
export TEMPLATE_REF=main
```

**Benefits of template bootstrap:**
- ✅ No GitHub token required for public repos
- ✅ Faster (shallow clone)
- ✅ Simpler configuration
- ✅ Works with any Git hosting (GitHub, GitLab, Bitbucket)

## References

- Implementation: [orchestrator/bootstrap.py](orchestrator/bootstrap.py)
- Path Configuration: [orchestrator/paths.py](orchestrator/paths.py)
- Integration: [orchestrator/main.py](orchestrator/main.py)
- Path Contract: [RUNPOD_PATH_CONTRACT.md](RUNPOD_PATH_CONTRACT.md)

---

**Last Updated**: 2026-01-16  
**Status**: Production Ready ✅
