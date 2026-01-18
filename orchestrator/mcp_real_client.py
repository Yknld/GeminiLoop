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

# Default timeout for MCP operations (30 seconds)
DEFAULT_MCP_TIMEOUT = 30.0


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
                
                line_bytes = await self.stdout.readline()
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
            raise Exception(f"MCP request timeout after {self.timeout}s: {method}")
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
    
    async def screenshot(self, filepath: Path) -> str:
        """Take screenshot"""
        logger.info(f"Screenshot: {filepath}")
        
        result = await self.call_tool("browser_take_screenshot", {
            "fullPage": True,
            "filename": str(filepath)
        })
        
        logger.info("Screenshot saved")
        return str(filepath)
    
    async def snapshot(self) -> Dict[str, Any]:
        """Get page snapshot"""
        logger.info("Getting page snapshot...")
        
        result = await self.call_tool("browser_snapshot", {})
        
        snapshot = {
            "title": result.get("title", ""),
            "text_content": result.get("textContent", "")[:500],
            "buttons": result.get("buttons", [])
        }
        
        logger.info(f"Snapshot: {len(snapshot['buttons'])} buttons")
        return snapshot
    
    async def get_console(self) -> list:
        """Get console messages"""
        logger.info("Getting console messages...")
        
        result = await self.call_tool("browser_console_messages", {})
        messages = result.get("messages", [])
        
        logger.info(f"Console: {len(messages)} messages")
        return messages
    
    async def evaluate(self, expression: str) -> Dict[str, Any]:
        """Evaluate JavaScript expression"""
        logger.debug(f"Evaluate: {expression[:100]}")
        
        result = await self.call_tool("browser_evaluate", {
            "expression": expression
        })
        
        return {"result": result}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call MCP tool"""
        logger.debug(f"Tool call: {tool_name}")
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
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
