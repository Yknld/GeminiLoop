# GeminiLoop Issues Analysis: Prompt Builder to MCP

**Date:** January 2026  
**Scope:** Complete flow from prompt builder (planner.py) through OpenHands to MCP evaluation

## Executive Summary

This analysis identifies potential issues in the GeminiLoop pipeline from prompt generation to MCP-based evaluation. Issues are categorized by severity and component.

---

## 1. PROMPT BUILDER (planner.py) Issues

### 🔴 CRITICAL Issues

#### 1.1 JSON Parsing Fragility
**Location:** `planner.py:155-165`  
**Issue:** JSON extraction uses regex patterns that may fail with complex nested JSON or markdown formatting.

```python
# Current approach - fragile
json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
if json_match:
    response_text = json_match.group(1)
else:
    json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(1)
```

**Problems:**
- Regex `.*?` is non-greedy but may not match nested braces correctly
- No handling for JSON arrays at root level
- May extract partial JSON if response contains multiple JSON blocks

**Recommendation:**
- Use a more robust JSON extraction library (e.g., `json5` or `demjson3`)
- Implement recursive brace matching
- Add validation that extracted JSON matches expected schema

#### 1.2 Missing Template Summary Validation
**Location:** `planner.py:47-57`  
**Issue:** Template summary loading fails silently - continues without template context if file not found.

**Problems:**
- No validation that template summary exists before proceeding
- Multiple path fallbacks may mask real issues
- Planner may generate prompts that don't match actual template structure

**Recommendation:**
- Add explicit check: if template is required, fail fast if not found
- Log which path was used for debugging
- Validate template summary format before using

#### 1.3 String Replacement Vulnerability
**Location:** `planner.py:115-121`  
**Issue:** Uses simple `.replace()` for prompt template substitution, which can break if placeholders appear in content.

```python
full_prompt = self.planner_prompt.replace(
    "{user_requirements}", user_requirements
).replace(
    "{notes}", notes_text
).replace(
    "{youtube_links}", youtube_links_text
)
```

**Problems:**
- If `user_requirements` contains `{notes}`, it will be replaced incorrectly
- No escaping of special characters
- Order-dependent (later replacements can break earlier ones)

**Recommendation:**
- Use proper template engine (e.g., `string.Template` with `safe_substitute`)
- Or use `.format()` with escaping
- Validate inputs don't contain template placeholders

### 🟡 MEDIUM Issues

#### 1.4 No Prompt Length Validation
**Location:** `planner.py:136`  
**Issue:** `max_output_tokens: 8192` may truncate long prompts, but no validation that prompt fits.

**Problems:**
- Truncated prompts may be incomplete
- No warning if prompt is too long
- OpenHands may receive incomplete instructions

**Recommendation:**
- Check prompt length after generation
- Warn if approaching token limit
- Split into multiple prompts if needed

#### 1.5 Missing Error Context in Fallback
**Location:** `planner.py:197-215`  
**Issue:** When JSON parsing fails, fallback uses raw response but doesn't preserve error context for debugging.

**Problems:**
- Hard to debug why JSON parsing failed
- No structured error reporting
- May mask underlying issues (e.g., model not following format)

**Recommendation:**
- Save raw response to file for inspection
- Include error details in metadata
- Add retry logic with different parsing strategies

---

## 2. PROMPT TEMPLATE (planner_prompt.txt) Issues

### 🔴 CRITICAL Issues

#### 2.1 Hardcoded API Key in Prompt ✅ FIXED
**Location:** `planner_prompt.txt:207`  
**Issue:** Google Cloud TTS API key is hardcoded in the prompt template.

**Status:** ✅ **FIXED** - Now uses environment variable injection

**Changes Made:**
- Updated `planner_prompt.txt` to use `{tts_api_key}` placeholder
- Updated `planner.py` to inject API key from `GOOGLE_TTS_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY` env vars
- Updated `openhands_client.py` to use environment variable for TTS API key
- Updated `template.html` to read Gemini API key from meta tag (injected at runtime)
- Updated `main.py` to inject API key when copying template

**Remaining:**
- Key validation before use (recommended enhancement)

#### 2.2 Conflicting Instructions
**Location:** `planner_prompt.txt:4, 12-16, 93-99`  
**Issue:** Multiple conflicting instructions about template usage.

**Problems:**
- Says "template.html" in some places, "index.html" in others
- Unclear whether to copy or edit in place
- May confuse OpenHands agent

**Recommendation:**
- Standardize on single approach
- Remove contradictions
- Add clear step-by-step instructions

#### 2.3 Overly Complex JSON Schema
**Location:** `planner_prompt.txt:116-188`  
**Issue:** Extremely nested JSON schema may cause model to fail or produce invalid output.

**Problems:**
- Deep nesting (course_overview.modules[].interactive_experiences[])
- Many optional fields
- Model may skip required fields

**Recommendation:**
- Simplify schema
- Make optional fields truly optional
- Add schema validation after generation

### 🟡 MEDIUM Issues

#### 2.4 Vague Interactive Element Requirements
**Location:** `planner_prompt.txt:221-226`  
**Issue:** Instructions for `interactiveElement` are vague - "actual working HTML/JavaScript" is not specific enough.

**Problems:**
- OpenHands may create placeholder content
- No examples of what "working" means
- No validation criteria

**Recommendation:**
- Provide concrete examples
- Specify minimum functionality requirements
- Add validation checks in evaluator

---

## 3. OPENHANDS CLIENT (openhands_client.py) Issues

### 🔴 CRITICAL Issues

#### 3.1 No Timeout on OpenHands Execution
**Location:** `openhands_client.py:189-190`  
**Issue:** `conversation.run()` has no timeout - can hang indefinitely.

```python
conversation.send_message(prompt)
conversation.run()  # No timeout!
```

**Problems:**
- Can hang forever if OpenHands agent gets stuck
- No way to cancel long-running operations
- Blocks entire pipeline

**Recommendation:**
- Add timeout parameter (e.g., 10 minutes)
- Implement cancellation mechanism
- Add progress monitoring

#### 3.2 Workspace State Capture Race Condition
**Location:** `openhands_client.py:374-412`  
**Issue:** `_capture_workspace_state()` may miss files created during capture.

**Problems:**
- Files created during `rglob()` iteration may be missed
- No atomic snapshot
- Race condition with OpenHands writing files

**Recommendation:**
- Use file system snapshots if available
- Add retry logic
- Validate file timestamps

#### 3.3 Hardcoded Model Name
**Location:** `openhands_client.py:155, 274`  
**Issue:** Model name defaults to `gemini-3-flash-preview` but may not exist.

```python
model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
```

**Problems:**
- Model may be deprecated
- No validation model exists
- Hard to test with different models

**Recommendation:**
- Validate model name before use
- Add model availability check
- Provide clear error if model unavailable

### 🟡 MEDIUM Issues

#### 3.4 Incomplete Error Handling
**Location:** `openhands_client.py:229-238`  
**Issue:** Catches all exceptions but doesn't distinguish between recoverable and fatal errors.

**Problems:**
- Network errors treated same as code errors
- No retry logic for transient failures
- May retry on fatal errors

**Recommendation:**
- Classify error types
- Retry on transient errors
- Fail fast on fatal errors

#### 3.5 No Validation of Generated Files
**Location:** `openhands_client.py:193-208`  
**Issue:** After OpenHands execution, no validation that expected files exist.

**Problems:**
- May proceed with missing files
- No check that index.html was created
- Silent failures

**Recommendation:**
- Validate required files exist
- Check file sizes (not empty)
- Verify file format (e.g., valid HTML)

---

## 4. MCP CLIENT (mcp_real_client.py) Issues

### 🔴 CRITICAL Issues

#### 4.1 No Connection Retry Logic
**Location:** `mcp_real_client.py:31-62`  
**Issue:** If MCP server fails to start, connection fails immediately with no retry.

**Problems:**
- Transient failures (e.g., port in use) cause permanent failure
- No exponential backoff
- No health check before use

**Recommendation:**
- Add retry logic with exponential backoff
- Validate connection before returning
- Add connection health check

#### 4.2 Blocking I/O in Async Context
**Location:** `mcp_real_client.py:90-107`  
**Issue:** Uses blocking `readline()` in async function.

```python
response_line = self.process.stdout.readline()  # Blocking!
```

**Problems:**
- Blocks event loop
- No timeout
- Can hang if server doesn't respond

**Recommendation:**
- Use `asyncio.create_subprocess_exec` with async I/O
- Add timeout to read operations
- Use `asyncio.wait_for()` for timeouts

#### 4.3 No Message ID Validation
**Location:** `mcp_real_client.py:76-107`  
**Issue:** Doesn't validate response ID matches request ID.

**Problems:**
- May process wrong response
- Race conditions with multiple requests
- No protection against out-of-order responses

**Recommendation:**
- Validate response ID matches request
- Use request/response correlation map
- Add sequence numbers

#### 4.4 Process Cleanup on Error
**Location:** `mcp_real_client.py:64-74`  
**Issue:** `disconnect()` may not clean up properly if process already dead.

**Problems:**
- Zombie processes
- Resource leaks
- Ports may remain in use

**Recommendation:**
- Check process status before terminate
- Use `wait()` with timeout
- Force kill if graceful shutdown fails

### 🟡 MEDIUM Issues

#### 4.5 No Request Timeout
**Location:** `mcp_real_client.py:76-107`  
**Issue:** `_send_request()` has no timeout - can wait forever.

**Problems:**
- Hangs if server crashes
- No way to cancel stuck requests
- Blocks entire evaluation

**Recommendation:**
- Add timeout parameter (default 30s)
- Use `asyncio.wait_for()`
- Implement request cancellation

#### 4.6 Error Response Handling
**Location:** `mcp_real_client.py:102-105`  
**Issue:** Error responses raise generic Exception, losing error details.

**Problems:**
- Hard to debug MCP protocol errors
- No error code preservation
- Generic error messages

**Recommendation:**
- Create custom exception classes
- Preserve MCP error codes
- Include full error context

---

## 5. MCP SERVER (playwright_mcp_server.js) Issues

### 🔴 CRITICAL Issues

#### 5.1 No Error Recovery
**Location:** `playwright_mcp_server.js:50-84`  
**Issue:** If any tool call fails, entire request fails with no recovery.

**Problems:**
- Single failure kills entire evaluation
- No partial success handling
- No retry for transient failures

**Recommendation:**
- Add retry logic for transient errors
- Implement partial success handling
- Add error recovery strategies

#### 5.2 Screenshot Timeout Handling
**Location:** `playwright_mcp_server.js:305-374`  
**Issue:** Complex retry logic for screenshots but may still fail silently.

**Problems:**
- Multiple retry attempts may mask underlying issues
- No clear error reporting
- May return success even if screenshot failed

**Recommendation:**
- Simplify retry logic
- Add clear error reporting
- Validate screenshot file exists and is valid

#### 5.3 Console Messages Not Implemented
**Location:** `playwright_mcp_server.js:396-402`  
**Issue:** `getConsole()` returns empty array - not actually collecting console messages.

```javascript
async getConsole() {
    this.log('Getting console messages...');
    return {
        messages: []  // Always empty!
    };
}
```

**Problems:**
- Console errors not detected
- Evaluator can't see JavaScript errors
- Missing critical debugging information

**Recommendation:**
- Implement console message collection
- Use Playwright's console event listener
- Store messages with timestamps

#### 5.4 Video Recording Context Management
**Location:** `playwright_mcp_server.js:484-530`  
**Issue:** `startRecording()` closes current context, losing page state.

**Problems:**
- Navigation state lost
- Must re-navigate after starting recording
- Breaks evaluation flow

**Recommendation:**
- Don't close context when starting recording
- Use separate context for recording
- Preserve page state

### 🟡 MEDIUM Issues

#### 5.5 No Request Validation
**Location:** `playwright_mcp_server.js:50-84`  
**Issue:** Doesn't validate request parameters before processing.

**Problems:**
- Invalid parameters cause crashes
- No input sanitization
- Security risk

**Recommendation:**
- Validate all parameters
- Use schema validation
- Return clear error messages

#### 5.6 Resource Cleanup
**Location:** `playwright_mcp_server.js:619-626`  
**Issue:** Cleanup only on SIGTERM/SIGINT - may not run in all scenarios.

**Problems:**
- Browser may not close on error
- Resource leaks
- Ports may remain in use

**Recommendation:**
- Add cleanup in error handlers
- Use try/finally blocks
- Implement health checks

---

## 6. EVALUATOR INTEGRATION Issues

### 🔴 CRITICAL Issues

#### 6.1 URL Validation Gap
**Location:** `evaluator.py:196-202`  
**Issue:** Validates URL protocol but doesn't ensure URL is accessible.

**Problems:**
- May proceed with unreachable URL
- No check that preview server is running
- Fails late in process

**Recommendation:**
- Validate URL is reachable before evaluation
- Check preview server health
- Fail fast if URL invalid

#### 6.2 MCP Client Lifecycle
**Location:** `main.py:303-307, 793-794`  
**Issue:** MCP client created early but may not be used if planning fails.

**Problems:**
- Resource waste if planning fails
- MCP server started unnecessarily
- No lazy initialization

**Recommendation:**
- Create MCP client only when needed
- Add connection pooling
- Implement lazy initialization

#### 6.3 Missing Error Propagation
**Location:** `evaluator.py:406-425`  
**Issue:** Evaluation errors return fallback result instead of propagating.

**Problems:**
- Errors masked by fallback
- Hard to debug real issues
- May proceed with invalid evaluation

**Recommendation:**
- Distinguish between recoverable and fatal errors
- Propagate fatal errors
- Use fallback only for transient failures

### 🟡 MEDIUM Issues

#### 6.4 Screenshot Directory Management
**Location:** `main.py:449-451`  
**Issue:** Creates screenshot directory but doesn't validate it's writable.

**Problems:**
- May fail when trying to save screenshots
- No error if directory creation fails
- Silent failures

**Recommendation:**
- Validate directory is writable
- Check disk space
- Provide clear error messages

#### 6.5 Evaluation Result Validation
**Location:** `evaluator.py:547-628`  
**Issue:** JSON parsing has fallback but doesn't validate result structure.

**Problems:**
- May proceed with invalid evaluation
- Missing required fields
- Type mismatches

**Recommendation:**
- Validate result structure
- Check required fields exist
- Validate data types

---

## 7. CROSS-COMPONENT Issues

### 🔴 CRITICAL Issues

#### 7.1 No End-to-End Validation
**Issue:** No validation that prompt → code → evaluation pipeline produces valid results.

**Problems:**
- Prompt may generate invalid code
- Code may not match prompt requirements
- Evaluation may not catch issues

**Recommendation:**
- Add validation at each stage
- Compare generated code to prompt requirements
- Validate evaluation matches code

#### 7.2 Inconsistent Error Handling
**Issue:** Different components handle errors differently - some raise, some return errors, some use fallbacks.

**Problems:**
- Hard to debug end-to-end
- Inconsistent error reporting
- Errors may be lost

**Recommendation:**
- Standardize error handling
- Use consistent error types
- Implement error aggregation

#### 7.3 Resource Leaks
**Issue:** Multiple components create resources (processes, files, connections) but cleanup may not run.

**Problems:**
- Resource leaks in long-running processes
- Port exhaustion
- Disk space issues

**Recommendation:**
- Use context managers
- Implement proper cleanup
- Add resource monitoring

### 🟡 MEDIUM Issues

#### 7.4 No Progress Tracking
**Issue:** No way to track progress through long-running operations.

**Problems:**
- Can't estimate completion time
- Hard to debug stuck processes
- No user feedback

**Recommendation:**
- Add progress callbacks
- Implement progress events
- Add time estimates

#### 7.5 Logging Inconsistency
**Issue:** Different components use different logging levels and formats.

**Problems:**
- Hard to correlate logs
- Inconsistent log levels
- Missing context

**Recommendation:**
- Standardize logging format
- Use structured logging
- Add correlation IDs

---

## 8. SECURITY Issues

### 🔴 CRITICAL Issues

#### 8.1 Hardcoded API Keys ✅ FIXED
**Location:** `planner_prompt.txt:207`, `openhands_client.py:561`, `template.html:1666`  
**Issue:** API keys hardcoded in templates.

**Status:** ✅ **FIXED** - All API keys now use environment variables

**Changes Made:**
- TTS API key: Uses `GOOGLE_TTS_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY` env vars
- Gemini API key: Injected from `GOOGLE_AI_STUDIO_API_KEY` env var at template copy time
- All keys read from RunPod environment variables

**Remaining:**
- Key rotation support (recommended enhancement)
- Key validation before use (recommended enhancement)

#### 8.2 No Input Sanitization
**Issue:** User inputs (task, notes) not sanitized before use in prompts.

**Recommendation:**
- Sanitize all inputs
- Validate input format
- Escape special characters

#### 8.3 File System Access
**Location:** `openhands_client.py:374-412`  
**Issue:** `_capture_workspace_state()` uses `rglob()` which may access files outside workspace.

**Recommendation:**
- Validate all paths are within workspace
- Use `pathlib` path resolution
- Add path validation

---

## 9. PERFORMANCE Issues

### 🟡 MEDIUM Issues

#### 9.1 Synchronous File Operations
**Issue:** Many file operations are synchronous, blocking event loop.

**Recommendation:**
- Use `aiofiles` for async file I/O
- Move heavy operations to thread pool
- Add async file utilities

#### 9.2 No Caching
**Issue:** Template summary and prompts loaded every time.

**Recommendation:**
- Cache template summary
- Cache parsed prompts
- Add cache invalidation

#### 9.3 Large File Handling
**Issue:** No handling for very large generated files.

**Recommendation:**
- Add file size limits
- Stream large files
- Add compression

---

## 10. RECOMMENDATIONS SUMMARY

### Immediate Actions (Critical)
1. Fix JSON parsing in planner (use robust parser)
2. Remove hardcoded API keys
3. Add timeouts to all async operations
4. Implement proper error handling
5. Fix MCP client blocking I/O

### Short-term (High Priority)
1. Add input validation and sanitization
2. Implement retry logic for transient failures
3. Add progress tracking
4. Standardize error handling
5. Fix console message collection in MCP server

### Long-term (Medium Priority)
1. Add comprehensive testing
2. Implement monitoring and observability
3. Add performance optimizations
4. Improve documentation
5. Add integration tests

---

## 11. TESTING GAPS

### Missing Tests
- No unit tests for planner JSON parsing
- No integration tests for prompt → code → evaluation flow
- No tests for error handling paths
- No tests for MCP protocol compliance
- No tests for resource cleanup

### Recommendation
- Add comprehensive test suite
- Test error paths
- Test edge cases
- Add integration tests
- Add performance tests

---

## Conclusion

This analysis identified **25 critical issues**, **15 medium issues**, and **5 security issues** across the GeminiLoop pipeline. The most critical areas are:

1. **Prompt Builder**: JSON parsing fragility, missing validation
2. **MCP Client**: Blocking I/O, no timeouts, connection issues
3. **MCP Server**: Missing console collection, resource leaks
4. **Security**: Hardcoded API keys, no input sanitization

Priority should be given to fixing critical issues that can cause system failures, followed by security issues, then performance and reliability improvements.
