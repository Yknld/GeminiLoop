# qa_browseruse_mcp

Browser automation layer using Playwright, providing a clean MCP interface for browser QA evaluation.

## Overview

This package replaces the brittle Gemini-controlled browser QA setup with a robust MCP-based layer powered by Playwright. It provides:

- **Persistent browser session** across tool calls
- **Stable selectors** for interactive elements (id, data-testid, aria-label, name, CSS path)
- **Comprehensive DOM snapshots** with interactive element discovery
- **Console error tracking** with proper filtering
- **Headless mode ready** for RunPod/CI environments

## Features

### Available Tools

- `navigate(url)` - Navigate to a URL
- `screenshot(path, return_base64=False)` - Take a screenshot
- `dom_snapshot(max_interactive=50)` - Get DOM snapshot with interactive elements
- `interactive_elements(max_interactive=50)` - Get list of interactive elements
- `click(selector)` - Click an element by selector
- `type(selector, text)` - Type text into an input field
- `wait_for(selector=None, text=None, timeout_ms=30000)` - Wait for selector or text
- `set_viewport(width, height)` - Set viewport size (replaces window.resizeTo)
- `get_url()` - Get current URL
- `evaluate_js(expression)` - Evaluate JavaScript expression
- `get_console()` - Get console messages
- `close()` - Close browser session

## Setup

### Local Development

1. Install Python 3.11+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install playwright
   playwright install chromium --with-deps
   ```

3. Start the MCP server:
   ```bash
   uvicorn qa_browseruse_mcp.server:app --host 127.0.0.1 --port 8000
   ```

4. Run smoke test:
   ```bash
   python -m qa_browseruse_mcp.smoke_test --url https://example.com --base_url http://127.0.0.1:8000
   ```

### RunPod Deployment

1. Build the Docker image:
   ```bash
   docker build -f Dockerfile.runpod -t qa_browseruse_mcp:runpod .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 qa_browseruse_mcp:runpod
   ```

   Or override the command to start the server:
   ```bash
   docker run -p 8000:8000 qa_browseruse_mcp:runpod \
     uvicorn qa_browseruse_mcp.server:app --host 0.0.0.0 --port 8000
   ```

## Usage

### In Evaluator Code

```python
from qa_browseruse_mcp.client import BrowserUseMCPClient

# Initialize client
client = BrowserUseMCPClient(base_url="http://127.0.0.1:8000")

# Navigate
await client.navigate("https://example.com")

# Take screenshot
await client.screenshot("screenshot.png")

# Get DOM snapshot
snapshot = await client.snapshot()
print(f"Title: {snapshot['title']}")
print(f"Interactive elements: {len(snapshot['interactive_elements'])}")

# Click an element
await client.click("button#submit")

# Type into input
await client.type_text("input[name='email']", "test@example.com")

# Get console messages
console = await client.get_console()
errors = [m for m in console if m.get("level") == "error"]

# Close client
await client.close()
```

### Compatibility with Old Interface

The client maintains compatibility with the old `mcp_client.call_tool()` interface:

```python
# Old way (still works)
result = await client.call_tool("browser_click", {"selector": "button"})
result = await client.call_tool("browser_snapshot", {})

# New way (preferred)
await client.click("button")
snapshot = await client.snapshot()
```

## Architecture

```
┌─────────────────┐
│   Evaluator     │
│  (Gemini/Agent) │
└────────┬────────┘
         │
         │ BrowserUseMCPClient
         │
┌────────▼────────┐
│  MCP Server     │
│   (FastAPI)     │
└────────┬────────┘
         │
         │ BrowserSession
         │
┌────────▼────────┐
│   Playwright    │
│   (Chromium)    │
└─────────────────┘
```

## Interactive Element Discovery

Interactive elements are discovered with stable selectors in this priority order:

1. `#id` - Element ID
2. `[data-testid="..."]` - Data test ID
3. `[aria-label="..."]` - ARIA label
4. `[name="..."]` - Name attribute
5. CSS path with `nth-of-type` - Fallback

Each element includes:
- `selector` - Stable selector
- `text` - Visible text
- `tag` - HTML tag name
- `role` - ARIA role (if present)
- `visible` - Whether element is visible
- `bbox` - Bounding box (x, y, width, height)
- `disabled` - Whether element is disabled
- `type` - Element type (button, link, input, etc.)

## Console Error Filtering

Console messages support both `level` and `type` fields for compatibility:

```python
# Both work:
errors = [m for m in console if m.get("level") == "error"]
errors = [m for m in console if m.get("type") == "error"]
```

## Notes

- **Headless mode**: Defaults to headless for RunPod/CI. Set `headless=False` in `BrowserSession` for local debugging.
- **Viewport**: Use `set_viewport()` instead of `window.resizeTo()` (which doesn't work in headless browsers).
- **Persistent session**: Browser session persists across tool calls. Call `close()` to end session.
- **Error handling**: All tools return `{success: bool, error: str}` format. Failures don't crash the server.

## Troubleshooting

### Screenshot timeouts
- Screenshots wait for `networkidle` state with timeout
- If timeout occurs, screenshot is retried with shorter timeout
- Final fallback uses minimal timeout (2s)

### Element not found
- Check selector is correct
- Ensure element is visible (not hidden by CSS)
- Try waiting for element: `await client.wait_for(selector="...")`

### Console messages not appearing
- Console messages are buffered from page load
- Call `get_console()` to retrieve buffered messages
- Messages are limited to last 1000 to prevent memory issues

## License

Same as parent project.
