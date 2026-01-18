"""
Real MCP Protocol Client

Implements JSON-RPC 2.0 over stdio for Playwright MCP server
"""

import json
import asyncio
import subprocess
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default timeout for MCP operations (60 seconds for general operations)
# Some operations like screenshots may need longer
DEFAULT_MCP_TIMEOUT = 60.0


class PlaywrightMCPClient:
    """
    MCP client for Playwright browser automation
    Spawns Node.js MCP server as subprocess
    """
    
    def __init__(self, server_path: Optional[Path] = None, timeout: float = DEFAULT_MCP_TIMEOUT):
        self.server_path = server_path or Path(__file__).parent / "playwright_mcp_server.js"
        self.process: Optional[asyncio.subprocess.Process] = None
        self.stdin: Optional[asyncio.StreamWriter] = None
        self.stdout: Optional[asyncio.StreamReader] = None
        self.message_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.timeout = timeout
        
        logger.info(f"Initializing Playwright MCP client")
        logger.info(f"Server: {self.server_path}")
        logger.info(f"Timeout: {timeout}s")
    
    async def connect(self):
        """Start MCP server and initialize connection"""
        logger.info("Starting Playwright MCP server...")
        
        # Start Node.js server using async subprocess
        self.process = await asyncio.create_subprocess_exec(
            "node", str(self.server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        
        logger.info(f"Process started (PID: {self.process.pid})")
        
        # Start response reader task
        self._response_reader_task = asyncio.create_task(self._read_responses())
        
        # Initialize MCP session
        init_result = await asyncio.wait_for(
            self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "gemini-loop",
                    "version": "1.0.0"
                }
            }),
            timeout=self.timeout
        )
        
        logger.info(f"MCP initialized: {init_result.get('serverInfo', {}).get('name')}")
        
        # Send initialized notification
        await self._send_notification("notifications/initialized", {})
        
        return init_result
    
    async def _read_responses(self):
        """Background task to read responses from MCP server"""
        try:
            while True:
                if not self.stdout:
                    break
                
                # Use readline with exception handling for large responses (e.g., DOM snapshots)
                # Default limit is ~64KB, but some responses (like DOM snapshots) can be larger
                try:
                    line_bytes = await self.stdout.readline()
                except ValueError as e:
                    if "chunk is longer than limit" in str(e) or "longer than limit" in str(e):
                        # Response too large for default limit, read in chunks until newline
                        logger.warning(f"Response exceeds default limit ({str(e)}), reading in chunks...")
                        chunks = []
                        found_newline = False
                        while not found_newline:
                            chunk = await self.stdout.read(8192)  # Read 8KB chunks
                            if not chunk:
                                break
                            if b'\n' in chunk:
                                # Split at first newline
                                parts = chunk.split(b'\n', 1)
                                chunks.append(parts[0])
                                line_bytes = b''.join(chunks) + b'\n'
                                found_newline = True
                                # Note: remaining data in parts[1] will be lost, but this is rare
                            else:
                                chunks.append(chunk)
                        if not found_newline:
                            # No newline found, use what we have
                            line_bytes = b''.join(chunks) if chunks else b''
                    else:
                        raise
                
                if not line_bytes:
                    break
                
                line = line_bytes.decode('utf-8').strip()
                if not line:
                    continue
                
                try:
                    response = json.loads(line)
                    request_id = response.get("id")
                    
                    if request_id and request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result(response)
                    else:
                        logger.warning(f"Received response for unknown request ID: {request_id}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse MCP response: {e}, line: {line[:100]}")
        except asyncio.CancelledError:
            logger.debug("Response reader task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error reading MCP responses: {e}")
            # Cancel all pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.set_exception(Exception(f"MCP connection error: {e}"))
            self.pending_requests.clear()
    
    async def disconnect(self):
        """Close MCP connection"""
        logger.info("Disconnecting from MCP server...")
        
        # Cancel response reader
        if hasattr(self, '_response_reader_task'):
            self._response_reader_task.cancel()
            try:
                await self._response_reader_task
            except asyncio.CancelledError:
                pass
        
        # Close streams
        if self.stdin:
            self.stdin.close()
            await self.stdin.wait_closed()
        # Note: StreamReader doesn't have close() method - process termination will handle it
        
        # Terminate process
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Process did not terminate gracefully, killing...")
                self.process.kill()
                await self.process.wait()
            logger.info("Process terminated")
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC 2.0 request with timeout and response validation"""
        if not self.stdin:
            raise Exception("MCP client not connected")
        
        self.message_id += 1
        request_id = self.message_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        logger.debug(f"MCP Request: {method} (ID: {request_id})")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            self.stdin.write(request_json.encode('utf-8'))
            await self.stdin.drain()
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=self.timeout)
            
            # Validate response ID matches request ID
            response_id = response.get("id")
            if response_id != request_id:
                raise Exception(f"Response ID mismatch: expected {request_id}, got {response_id}")
            
            # Check for errors
            if "error" in response:
                error = response["error"]
                logger.error(f"MCP Error: {error}")
                raise Exception(f"MCP Error: {error.get('message', 'Unknown error')} (code: {error.get('code', 'N/A')})")
            
            return response.get("result", {})
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise Exception(f"MCP request timeout after {request_timeout}s: {method}")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise
    
    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send JSON-RPC 2.0 notification (no response expected)"""
        if not self.stdin:
            raise Exception("MCP client not connected")
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        notification_json = json.dumps(notification) + "\n"
        self.stdin.write(notification_json.encode('utf-8'))
        await self.stdin.drain()
    
    async def navigate(self, url: str) -> bool:
        """Navigate to URL"""
        logger.info(f"Navigate: {url}")
        
        try:
            result = await self.call_tool("browser_navigate", {"url": url})
            logger.info(f"Loaded: {result.get('title', 'N/A')}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    async def screenshot(self, filepath: Path, timeout: Optional[float] = None) -> str:
        """Take screenshot with extended timeout for slow pages"""
        logger.info(f"Screenshot: {filepath}")
        
        # Screenshots can be slow, use longer timeout (90s default, or provided)
        screenshot_timeout = timeout if timeout is not None else 90.0
        
        result = await self.call_tool("browser_take_screenshot", {
            "fullPage": True,
            "filename": str(filepath)
        }, timeout=screenshot_timeout)
        
        logger.info("Screenshot saved")
        return str(filepath)
    
    async def snapshot(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Get page snapshot with extended timeout for large pages"""
        logger.info("Getting page snapshot...")
        
        # Snapshots can be slow on large pages, use longer timeout (90s default)
        snapshot_timeout = timeout if timeout is not None else 90.0
        
        result = await self.call_tool("browser_snapshot", {}, timeout=snapshot_timeout)
        
        snapshot = {
            "title": result.get("title", ""),
            "text_content": result.get("textContent", "")[:500],
            "buttons": result.get("buttons", [])
        }
        
        logger.info(f"Snapshot: {len(snapshot['buttons'])} buttons")
        return snapshot
    
    async def get_console(self, timeout: Optional[float] = None) -> list:
        """Get console messages with extended timeout"""
        logger.info("Getting console messages...")
        
        # Console messages can be slow, use longer timeout (60s default)
        console_timeout = timeout if timeout is not None else 60.0
        
        result = await self.call_tool("browser_console_messages", {}, timeout=console_timeout)
        messages = result.get("messages", [])
        
        logger.info(f"Console: {len(messages)} messages")
        return messages
    
    async def evaluate(self, expression: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Evaluate JavaScript expression with extended timeout for complex expressions"""
        logger.debug(f"Evaluate: {expression[:100]}")
        
        # Complex evaluations (like DOM snapshots) can be slow, use longer timeout (90s default)
        eval_timeout = timeout if timeout is not None else 90.0
        
        result = await self.call_tool("browser_evaluate", {
            "expression": expression
        }, timeout=eval_timeout)
        
        return {"result": result}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: Optional[float] = None) -> Any:
        """Call MCP tool"""
        logger.debug(f"Tool call: {tool_name}")
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        }, timeout=timeout)
        
        return result
    
    async def start_recording(self, video_path: str) -> bool:
        """Start video recording"""
        logger.info(f"Starting video recording: {video_path}")
        
        result = await self.call_tool("browser_start_recording", {
            "videoPath": video_path
        })
        
        return result.get("success", False)
    
    async def stop_recording(self) -> Optional[str]:
        """Stop video recording and return video path"""
        logger.info("Stopping video recording...")
        
        result = await self.call_tool("browser_stop_recording", {})
        
        if result.get("success"):
            return result.get("videoPath")
        return None
