# Fixes Applied to GeminiLoop

## Fix #1: Remove Hardcoded API Keys ✅

**Date:** January 2026  
**Issue:** Hardcoded API keys in multiple files pose security risks and prevent key rotation.

### Files Modified

1. **`orchestrator/prompts/planner_prompt.txt`**
   - Changed: Replaced hardcoded TTS API key with `{tts_api_key}` placeholder
   - Line: 207

2. **`orchestrator/planner.py`**
   - Changed: Added API key injection from environment variables
   - Reads from: `GOOGLE_TTS_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY`
   - Injects key when building prompt
   - Lines: 108-112, 115-121

3. **`orchestrator/openhands_client.py`**
   - Changed: Replaced hardcoded TTS API key with environment variable lookup
   - Reads from: `GOOGLE_TTS_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY`
   - Lines: 559-561

4. **`template.html`**
   - Changed: Replaced hardcoded Gemini API key with meta tag approach
   - Uses: `<meta name="gemini-api-key" content="{GEMINI_API_KEY}">`
   - JavaScript reads from meta tag at runtime
   - Lines: 6, 1666-1669

5. **`orchestrator/main.py`**
   - Changed: Added API key injection when copying template
   - Replaces `{GEMINI_API_KEY}` placeholder with actual key from environment
   - Lines: 348-365

---

## Fix #2: Robust JSON Parsing ✅

**Date:** January 2026  
**Issue:** Fragile regex-based JSON extraction fails with nested JSON or complex markdown.

### Files Modified

1. **`orchestrator/planner.py`**
   - Added: `_extract_json_from_text()` method with recursive brace matching
   - Added: `_is_valid_json()` validation method
   - Replaced: Fragile regex patterns with robust extraction
   - Lines: 59-122, 163-175

### Improvements

- ✅ Handles nested JSON objects correctly
- ✅ Supports JSON in markdown code blocks
- ✅ Validates extracted JSON before parsing
- ✅ Finds JSON even when surrounded by extra text
- ✅ More reliable than regex approach

---

## Fix #3: String Replacement Vulnerability ✅

**Date:** January 2026  
**Issue:** Simple `.replace()` can break if placeholders appear in replacement values.

### Files Modified

1. **`orchestrator/planner.py`**
   - Changed: Safer replacement method with conflict detection
   - Added: Validation to detect placeholder conflicts
   - Lines: 130-150

### Improvements

- ✅ Detects if placeholders appear in replacement values
- ✅ Warns about potential conflicts
- ✅ More robust than simple string replacement

---

## Fix #4: Blocking I/O in MCP Client ✅

**Date:** January 2026  
**Issue:** Blocking `readline()` in async function blocks event loop.

### Files Modified

1. **`orchestrator/mcp_real_client.py`**
   - Changed: Converted from `subprocess.Popen` to `asyncio.create_subprocess_exec`
   - Added: Async response reader task (`_read_responses()`)
   - Added: Request/response correlation using futures
   - Lines: 23-29, 31-95, 76-140

### Improvements

- ✅ Fully async I/O (no blocking calls)
- ✅ Background task reads responses
- ✅ Request/response correlation with futures
- ✅ Proper cleanup on disconnect

---

## Fix #5: Add Timeouts to MCP Operations ✅

**Date:** January 2026  
**Issue:** MCP operations can hang indefinitely if server doesn't respond.

### Files Modified

1. **`orchestrator/mcp_real_client.py`**
   - Added: `timeout` parameter to `__init__` (default 30s)
   - Added: `asyncio.wait_for()` around all requests
   - Added: Timeout error handling
   - Lines: 23, 48-55, 76-140

### Improvements

- ✅ Configurable timeout (default 30s)
- ✅ All MCP requests have timeout protection
- ✅ Clear timeout error messages
- ✅ Prevents indefinite hangs

---

## Fix #6: Console Message Collection ✅

**Date:** January 2026  
**Issue:** Console messages not collected - always returns empty array.

### Files Modified

1. **`orchestrator/playwright_mcp_server.js`**
   - Added: Console message storage (`consoleMessages` array)
   - Added: `page.on('console')` event listener
   - Added: `page.on('pageerror')` event listener
   - Updated: `getConsole()` to return actual messages
   - Lines: 18, 120-145, 396-410

### Improvements

- ✅ Collects all console messages (log, error, warning, info)
- ✅ Collects page errors
- ✅ Includes timestamps and locations
- ✅ Limits to last 1000 messages (prevents memory issues)
- ✅ Returns error/warning counts

---

## Fix #7: OpenHands Execution Timeout ✅

**Date:** January 2026  
**Issue:** OpenHands execution can hang indefinitely.

### Files Modified

1. **`orchestrator/openhands_client.py`**
   - Added: Timeout support using threading
   - Added: `OPENHANDS_TIMEOUT_SECONDS` environment variable (default 600s)
   - Applied to: Both `generate_code()` and `apply_patch_plan()`
   - Lines: 12-13, 189-210, 304-325

### Improvements

- ✅ Configurable timeout (default 10 minutes)
- ✅ Prevents indefinite hangs
- ✅ Clear timeout error messages
- ✅ Works with synchronous OpenHands API

---

## Summary of All Fixes

### Security Fixes
- ✅ Removed all hardcoded API keys
- ✅ Keys now read from environment variables
- ✅ Safe template replacement

### Reliability Fixes
- ✅ Robust JSON parsing
- ✅ Async I/O in MCP client
- ✅ Timeouts on all long-running operations
- ✅ Console message collection

### Code Quality
- ✅ Better error handling
- ✅ Request/response correlation
- ✅ Proper resource cleanup

---

## Environment Variables

For RunPod deployment, set these environment variables:

```bash
# Required: Gemini API key
GOOGLE_AI_STUDIO_API_KEY=your_api_key_here

# Optional: Separate TTS API key (falls back to GOOGLE_AI_STUDIO_API_KEY)
GOOGLE_TTS_API_KEY=your_tts_key_here

# Optional: OpenHands timeout (default: 600 seconds = 10 minutes)
OPENHANDS_TIMEOUT_SECONDS=600

# Optional: MCP client timeout (default: 30 seconds)
# Set via PlaywrightMCPClient(timeout=30.0) in code
```

---

## Testing Recommendations

1. **Test API key injection:**
   ```bash
   export GOOGLE_AI_STUDIO_API_KEY="test_key"
   python -m orchestrator.planner "Test task"
   # Verify no hardcoded keys in output
   ```

2. **Test JSON parsing:**
   - Test with nested JSON
   - Test with markdown-wrapped JSON
   - Test with extra text around JSON

3. **Test MCP timeouts:**
   - Verify requests timeout after 30s if server hangs
   - Verify console messages are collected

4. **Test OpenHands timeout:**
   - Set `OPENHANDS_TIMEOUT_SECONDS=10` for quick test
   - Verify timeout error is raised

---

## Next Steps

Recommended additional fixes:
1. Add key validation before use
2. Add retry logic for transient failures
3. Add progress tracking for long operations
4. Add comprehensive error logging
5. Add integration tests
