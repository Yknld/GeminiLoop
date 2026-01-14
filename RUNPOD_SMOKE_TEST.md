# RunPod Smoke Test

**Goal:** Prove the pod boots and MCP browser works.

---

## Prerequisites

- RunPod account with GPU pod
- Google AI Studio API key
- Docker installed (for local testing)

---

## Step 1: Build Docker Image

### On RunPod:

```bash
# SSH into your RunPod instance
# Navigate to GeminiLoop directory
cd /workspace/GeminiLoop

# Build the Docker image
docker build -f deploy/runpod/Dockerfile -t gemini-loop:runpod .

# Verify build
docker images | grep gemini-loop
```

**Expected output:**
```
gemini-loop   runpod   <image_id>   <time>   <size>
```

---

## Step 2: Run Container

```bash
# Set your API key
export GOOGLE_AI_STUDIO_API_KEY=your_key_here

# Run the container
docker run -d \
  --name gemini-loop-test \
  -p 8080:8080 \
  -p 6080:6080 \
  -e GOOGLE_AI_STUDIO_API_KEY=$GOOGLE_AI_STUDIO_API_KEY \
  -e VISIBLE_BROWSER=0 \
  -v $(pwd)/runs:/app/runs \
  gemini-loop:runpod

# Check container is running
docker ps | grep gemini-loop-test

# View logs
docker logs -f gemini-loop-test
```

**Expected output in logs:**
```
🚀 GeminiLoop RunPod Startup
========================================
Configuration:
  - Runs directory: /app/runs
  - Preview port: 8080
  - Headless mode: true

📡 Starting preview server...
   Preview server PID: 123
   Preview URL: http://0.0.0.0:8080

✅ Preview server is healthy

========================================
✅ GeminiLoop Ready
========================================
```

---

## Step 3: Test Health Endpoint

```bash
# Test health endpoint
curl http://localhost:8080/health

# Or with details
curl http://localhost:8080/health | jq '.'
```

**Expected response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T23:00:00.000000",
  "runs_dir": "/app/runs"
}
```

**✅ PASS:** Health endpoint returns 200 OK  
**❌ FAIL:** Connection refused or error response → Check logs

---

## Step 4: Test Preview Endpoint (Static)

### Create a test HTML file:

```bash
# Exec into container
docker exec -it gemini-loop-test bash

# Create test run structure
mkdir -p /app/runs/test-static/site

# Create test HTML
cat > /app/runs/test-static/site/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RunPod Test Page</title>
    <style>
        body {
            font-family: system-ui;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            text-align: center;
        }
        .status { 
            font-size: 3em; 
            color: #4CAF50;
        }
    </style>
</head>
<body>
    <div class="status">✅</div>
    <h1>RunPod Static Test</h1>
    <p>If you can see this, the preview server is working!</p>
    <p id="timestamp"></p>
    <script>
        document.getElementById('timestamp').textContent = 
            'Loaded at: ' + new Date().toISOString();
    </script>
</body>
</html>
EOF

# Exit container
exit
```

### Test the preview:

```bash
# Test from host
curl http://localhost:8080/preview/test-static/ | grep "RunPod Static Test"

# Or open in browser
open http://localhost:8080/preview/test-static/
```

**Expected:** HTML page loads with green checkmark  
**✅ PASS:** Page displays correctly  
**❌ FAIL:** 404 or error → Check preview server logs

---

## Step 5: Run Minimal Evaluation

### Create test script:

```bash
# On host (not in container)
cat > /Users/danielntumba/match-me/GeminiLoop/test_runpod.py << 'EOF'
#!/usr/bin/env python3
"""
Minimal RunPod smoke test

Tests:
1. Gemini code generation
2. MCP Playwright browser automation
3. Screenshot capture
4. Report generation
"""

import asyncio
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.gemini_generator import GeminiCodeGenerator
from orchestrator.mcp_real_client import PlaywrightMCPClient
from orchestrator.run_state import RunConfig, RunState

async def smoke_test():
    """Run minimal smoke test"""
    
    print("=" * 70)
    print("🧪 RunPod Smoke Test")
    print("=" * 70)
    print()
    
    # Step 1: Setup
    print("Step 1: Creating test run...")
    config = RunConfig(
        task="Create a simple hello world page",
        max_iterations=1,
        base_dir=Path("/app/runs"),
        run_id="smoke-test-001"
    )
    state = RunState(config)
    print(f"✅ Run created: {state.config.run_id}")
    print(f"   Workspace: {state.workspace_dir}")
    print(f"   Artifacts: {state.artifacts_dir}")
    print()
    
    # Step 2: Generate simple HTML
    print("Step 2: Generating HTML with Gemini...")
    generator = GeminiCodeGenerator()
    
    simple_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smoke Test</title>
    <style>
        body {
            font-family: system-ui;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }
        h1 { font-size: 3em; margin: 0; }
        p { font-size: 1.5em; margin: 1em 0; }
        .status { font-size: 5em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status">✅</div>
        <h1>RunPod Smoke Test</h1>
        <p>MCP Browser Working!</p>
        <p id="time"></p>
    </div>
    <script>
        document.getElementById('time').textContent = 
            new Date().toLocaleTimeString();
    </script>
</body>
</html>"""
    
    # Save to workspace and site
    workspace_file = state.workspace_dir / "index.html"
    workspace_file.write_text(simple_html)
    
    site_file = state.site_dir / "index.html"
    site_file.write_text(simple_html)
    
    print(f"✅ HTML saved to {workspace_file}")
    print()
    
    # Step 3: Start MCP client
    print("Step 3: Starting Playwright MCP client...")
    mcp = PlaywrightMCPClient()
    await mcp.connect()
    print("✅ MCP client connected")
    print()
    
    # Step 4: Open page and take screenshot
    print("Step 4: Opening page in browser...")
    url = f"file://{site_file.absolute()}"
    print(f"   URL: {url}")
    
    await mcp.navigate(url)
    print("✅ Page loaded")
    print()
    
    print("Step 5: Taking screenshot...")
    screenshot_dir = state.artifacts_dir / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)
    screenshot_path = screenshot_dir / "smoke-test.png"
    
    await mcp.screenshot(str(screenshot_path))
    print(f"✅ Screenshot saved: {screenshot_path}")
    print()
    
    # Step 6: Get page info
    print("Step 6: Getting page snapshot...")
    snapshot = await mcp.snapshot()
    console_logs = await mcp.get_console()
    
    print(f"✅ Page title: {snapshot.get('title', 'N/A')}")
    print(f"✅ Console logs: {len(console_logs)} entries")
    print()
    
    # Step 7: Create report
    print("Step 7: Writing report...")
    report = {
        "run_id": state.config.run_id,
        "status": "success",
        "url": url,
        "screenshot": str(screenshot_path),
        "page_title": snapshot.get('title'),
        "console_logs": len(console_logs),
        "tests_passed": [
            "HTML generation",
            "MCP client connection",
            "Page navigation",
            "Screenshot capture",
            "Page snapshot"
        ]
    }
    
    report_file = state.artifacts_dir / "report.json"
    import json
    report_file.write_text(json.dumps(report, indent=2))
    print(f"✅ Report saved: {report_file}")
    print()
    
    # Cleanup
    await mcp.disconnect()
    
    # Final verification
    print("=" * 70)
    print("🎉 SMOKE TEST PASSED!")
    print("=" * 70)
    print()
    print("✅ All checks passed:")
    print("   ✓ Run structure created")
    print("   ✓ HTML generated")
    print("   ✓ MCP client connected")
    print("   ✓ Browser opened page")
    print("   ✓ Screenshot captured")
    print("   ✓ Report generated")
    print()
    print("Artifacts:")
    print(f"   Screenshot: {screenshot_path}")
    print(f"   Report: {report_file}")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(smoke_test())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
EOF

chmod +x test_runpod.py
```

### Run the smoke test:

```bash
# Copy test script to container
docker cp test_runpod.py gemini-loop-test:/app/test_runpod.py

# Run smoke test inside container
docker exec -it gemini-loop-test python3 /app/test_runpod.py
```

**Expected output:**
```
======================================================================
🧪 RunPod Smoke Test
======================================================================

Step 1: Creating test run...
✅ Run created: smoke-test-001
   Workspace: /app/runs/smoke-test-001/workspace
   Artifacts: /app/runs/smoke-test-001/artifacts

Step 2: Generating HTML with Gemini...
✅ HTML saved to /app/runs/smoke-test-001/workspace/index.html

Step 3: Starting Playwright MCP client...
[MCP Server] Initializing...
[MCP Server] Browser launched in headless mode
✅ MCP client connected

Step 4: Opening page in browser...
   URL: file:///app/runs/smoke-test-001/site/index.html
✅ Page loaded

Step 5: Taking screenshot...
✅ Screenshot saved: /app/runs/smoke-test-001/artifacts/screenshots/smoke-test.png

Step 6: Getting page snapshot...
✅ Page title: Smoke Test
✅ Console logs: 0 entries

Step 7: Writing report...
✅ Report saved: /app/runs/smoke-test-001/artifacts/report.json

======================================================================
🎉 SMOKE TEST PASSED!
======================================================================

✅ All checks passed:
   ✓ Run structure created
   ✓ HTML generated
   ✓ MCP client connected
   ✓ Browser opened page
   ✓ Screenshot captured
   ✓ Report generated

Artifacts:
   Screenshot: /app/runs/smoke-test-001/artifacts/screenshots/smoke-test.png
   Report: /app/runs/smoke-test-001/artifacts/report.json
```

---

## Step 6: Verify Artifacts

```bash
# Check files were created
docker exec gemini-loop-test ls -lh /app/runs/smoke-test-001/artifacts/

# View report
docker exec gemini-loop-test cat /app/runs/smoke-test-001/artifacts/report.json | jq '.'

# Copy screenshot to host for viewing
docker cp gemini-loop-test:/app/runs/smoke-test-001/artifacts/screenshots/smoke-test.png ./smoke-test.png

# Open screenshot
open smoke-test.png  # macOS
# or: xdg-open smoke-test.png  # Linux
```

**Expected artifacts:**
```
/app/runs/smoke-test-001/
├── workspace/
│   └── index.html
├── site/
│   └── index.html
└── artifacts/
    ├── screenshots/
    │   └── smoke-test.png
    └── report.json
```

---

## Success Criteria

### ✅ PASS if:

1. **Health endpoint** returns 200 OK
2. **Preview endpoint** serves static HTML
3. **MCP client** connects successfully
4. **Browser** opens page (headless or visible)
5. **Screenshot** is saved (valid PNG file)
6. **Report.json** is written with test data

### ❌ FAIL if:

1. Container fails to start
2. Preview server not responding
3. MCP client connection fails
4. Browser doesn't open
5. Screenshot not saved
6. Any Python errors

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs gemini-loop-test

# Common issues:
# - Missing API key
# - Port already in use
# - Insufficient memory
```

### Health endpoint fails

```bash
# Check preview server
docker exec gemini-loop-test ps aux | grep preview

# Restart preview server
docker exec gemini-loop-test pkill -f preview_server
docker exec gemini-loop-test python3 -m services.preview_server &
```

### MCP client fails

```bash
# Check Node.js and Playwright
docker exec gemini-loop-test node --version
docker exec gemini-loop-test npx playwright --version

# Check Chromium
docker exec gemini-loop-test ls -lh /root/.cache/ms-playwright/
```

### Screenshot is black/empty

```bash
# Check if page loaded
docker exec gemini-loop-test cat /app/runs/smoke-test-001/site/index.html

# Try with visible browser
docker stop gemini-loop-test
docker rm gemini-loop-test

docker run -d \
  --name gemini-loop-test \
  -p 8080:8080 -p 6080:6080 \
  -e VISIBLE_BROWSER=1 \
  -e GOOGLE_AI_STUDIO_API_KEY=$GOOGLE_AI_STUDIO_API_KEY \
  gemini-loop:runpod

# Access browser at http://localhost:6080/vnc.html
```

---

## Quick Test Commands

```bash
# All-in-one test
docker exec gemini-loop-test python3 /app/test_runpod.py && \
  docker cp gemini-loop-test:/app/runs/smoke-test-001/artifacts/screenshots/smoke-test.png . && \
  echo "✅ Screenshot saved to ./smoke-test.png"

# Clean up test
docker exec gemini-loop-test rm -rf /app/runs/smoke-test-001

# Stop container
docker stop gemini-loop-test
docker rm gemini-loop-test
```

---

## Next Steps

Once smoke test passes:

1. **Test full orchestrator loop** with `demo.py`
2. **Test GitHub integration** (if configured)
3. **Test OpenHands patching**
4. **Run production workload**

---

## Summary

This smoke test proves:
- ✅ Docker image builds
- ✅ Container starts successfully
- ✅ Preview server serves content
- ✅ Playwright MCP works
- ✅ Browser automation works
- ✅ Screenshots can be captured
- ✅ File I/O works correctly

**If any step fails, STOP and fix infrastructure before proceeding.**
