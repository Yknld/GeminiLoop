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


class PlaywrightMCPClient:
    """
    MCP client for Playwright browser automation
    Spawns Node.js MCP server as subprocess
    """
    
    def __init__(self, server_path: Optional[Path] = None):
        self.server_path = server_path or Path(__file__).parent / "playwright_mcp_server.js"
        self.process: Optional[subprocess.Popen] = None
        self.message_id = 0
        
        logger.info(f"Initializing Playwright MCP client")
        logger.info(f"Server: {self.server_path}")
    
    async def connect(self):
        """Start MCP server and initialize connection"""
        logger.info("Starting Playwright MCP server...")
        
        # Start Node.js server
        self.process = subprocess.Popen(
            ["node", str(self.server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        logger.info(f"Process started (PID: {self.process.pid})")
        
        # Initialize MCP session
        init_result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "gemini-loop",
                "version": "1.0.0"
            }
        })
        
        logger.info(f"MCP initialized: {init_result.get('serverInfo', {}).get('name')}")
        
        # Send initialized notification
        await self._send_notification("notifications/initialized", {})
        
        return init_result
    
    async def disconnect(self):
        """Close MCP connection"""
        logger.info("Disconnecting from MCP server...")
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info("Process terminated")
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC 2.0 request"""
        self.message_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params
        }
        
        logger.debug(f"MCP Request: {method}")
        
        # Send request
        request_json = json.dumps(request)
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        
        if not response_line:
            raise Exception("MCP server closed connection")
        
        response = json.loads(response_line)
        
        if "error" in response:
            error = response["error"]
            logger.error(f"MCP Error: {error}")
            raise Exception(f"MCP Error: {error.get('message', 'Unknown error')}")
        
        return response.get("result", {})
    
    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send JSON-RPC 2.0 notification (no response expected)"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()
    
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
