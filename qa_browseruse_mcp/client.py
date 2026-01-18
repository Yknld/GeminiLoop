"""
BrowserUse MCP Client

Client wrapper for evaluators to use the BrowserUse MCP server.
Provides a clean interface matching the old mcp_client API.

Supports two modes:
1. In-process mode (default): Creates browser session directly, no server needed
2. Server mode: Connects to MCP server via HTTP
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from .types import SimpleResponse, SnapshotResponse, InteractiveElement, ConsoleMessage
from .browser_session import BrowserSession

logger = logging.getLogger(__name__)


class BrowserUseMCPClient:
    """
    Client for BrowserUse MCP server
    
    Provides methods matching the old mcp_client interface for easy migration.
    
    Can work in two modes:
    - In-process: Direct browser session (default, no server needed)
    - Server: HTTP client connecting to MCP server
    """
    
    def __init__(self, base_url: Optional[str] = None, headless: bool = True):
        """
        Initialize client
        
        Args:
            base_url: Base URL of the MCP server. If None, uses in-process mode.
            headless: Whether to run browser in headless mode (for in-process mode)
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self._session: Optional[Any] = None
        self._browser_session: Optional[BrowserSession] = None
        self._in_process = base_url is None
        
        if self._in_process:
            logger.info("BrowserUseMCPClient: Using in-process mode (no server)")
            self._browser_session = BrowserSession(headless=headless)
        else:
            logger.info(f"BrowserUseMCPClient: Using server mode: {self.base_url}")
            if not HAS_AIOHTTP:
                raise ImportError("aiohttp is required for server mode. Install with: pip install aiohttp")
    
    async def _ensure_session(self):
        """Ensure HTTP session is created (server mode only)"""
        if not self._in_process:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
    
    async def _call_tool(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call a tool - either in-process or via server"""
        if self._in_process:
            # In-process mode: call browser session directly
            if not self._browser_session:
                raise RuntimeError("Browser session not initialized")
            
            # Map tool names to browser_session methods
            if tool == "navigate":
                result = await self._browser_session.navigate(args.get("url", ""))
            elif tool == "set_viewport":
                result = await self._browser_session.set_viewport(args.get("width", 1440), args.get("height", 900))
            elif tool == "screenshot":
                result = await self._browser_session.screenshot(path=args.get("path"), return_base64=args.get("return_base64", False))
            elif tool == "dom_snapshot":
                result = await self._browser_session.dom_snapshot(max_interactive=args.get("max_interactive", 50))
            elif tool == "click":
                result = await self._browser_session.click(args.get("selector", ""))
            elif tool == "type":
                result = await self._browser_session.type(args.get("selector", ""), args.get("text", ""))
            elif tool == "wait_for":
                result = await self._browser_session.wait_for(
                    selector=args.get("selector"),
                    text=args.get("text"),
                    timeout_ms=args.get("timeout_ms", 30000)
                )
            elif tool == "get_url":
                result = await self._browser_session.get_url()
            elif tool == "evaluate_js":
                result = await self._browser_session.evaluate_js(args.get("expression", ""))
            elif tool == "get_console":
                messages = await self._browser_session.get_console()
                result = SimpleResponse(success=True, result=[msg.model_dump() for msg in messages])
            elif tool == "start_recording":
                video_path = args.get("video_path") or args.get("videoPath")
                result = await self._browser_session.start_recording(video_path)
            elif tool == "stop_recording":
                result = await self._browser_session.stop_recording()
            elif tool == "close":
                result = await self._browser_session.close()
            else:
                result = SimpleResponse(success=False, error=f"Unknown tool: {tool}")
            
            return result.model_dump() if hasattr(result, 'model_dump') else result
        else:
            # Server mode: call via HTTP
            await self._ensure_session()
            
            url = f"{self.base_url}/call_tool"
            payload = {"tool": tool, "args": args or {}}
            
            try:
                # In server mode, aiohttp is guaranteed to be available (checked in __init__)
                timeout = aiohttp.ClientTimeout(total=120)
                async with self._session.post(url, json=payload, timeout=timeout) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data
            except Exception as e:
                logger.error(f"Tool call failed: {tool} - {e}")
                return {"success": False, "error": str(e)}
    
    async def connect(self):
        """Connect/initialize the client (for compatibility with old interface)"""
        if self._in_process:
            if self._browser_session and not self._browser_session._initialized:
                await self._browser_session.start()
        # Server mode doesn't need explicit connection
        return True
    
    async def disconnect(self):
        """Disconnect/close the client (for compatibility with old interface)"""
        if self._in_process:
            if self._browser_session:
                await self._browser_session.close()
        else:
            await self.close()
    
    async def navigate(self, url: str) -> bool:
        """
        Navigate to a URL
        
        Returns:
            True if successful, False otherwise
        """
        result = await self._call_tool("navigate", {"url": url})
        return result.get("success", False)
    
    async def screenshot(self, filepath: Union[str, Path], timeout: Optional[float] = None) -> str:
        """
        Take a screenshot
        
        Args:
            filepath: Path to save screenshot
            timeout: Optional timeout (not used in HTTP client, but kept for compatibility)
        
        Returns:
            Path to saved screenshot
        """
        path_str = str(filepath)
        result = await self._call_tool("screenshot", {"path": path_str, "return_base64": False})
        if result.get("success"):
            return path_str
        else:
            raise Exception(f"Screenshot failed: {result.get('error')}")
    
    async def snapshot(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Get page snapshot
        
        Args:
            timeout: Optional timeout (not used in HTTP client, but kept for compatibility)
        
        Returns:
            Snapshot dictionary with title, text_content, buttons, etc.
        """
        result = await self._call_tool("dom_snapshot", {})
        
        if result.get("success"):
            # Convert to old format for compatibility
            snapshot = {
                "title": result.get("title", ""),
                "textContent": result.get("visible_text_snippet", ""),
                "buttons": [
                    el.get("text", "") for el in result.get("interactive_elements", [])
                    if el.get("tag") == "button"
                ],
                "interactive_elements": result.get("interactive_elements", []),
            }
            return snapshot
        else:
            raise Exception(f"Snapshot failed: {result.get('error')}")
    
    async def get_console(self, timeout: Optional[float] = None) -> List[Dict[str, str]]:
        """
        Get console messages
        
        Args:
            timeout: Optional timeout (not used in HTTP client, but kept for compatibility)
        
        Returns:
            List of console messages in old format: [{"type": "...", "message": "..."}, ...]
        """
        result = await self._call_tool("get_console", {})
        
        if result.get("success"):
            messages = result.get("result", [])
            # Convert to old format for compatibility
            return [
                {
                    "type": msg.get("level", "log"),
                    "message": msg.get("text", ""),
                    "level": msg.get("level", "log"),  # Support both fields
                }
                for msg in messages
            ]
        else:
            return []
    
    async def evaluate(self, expression: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Evaluate JavaScript expression
        
        Args:
            expression: JavaScript expression to evaluate
            timeout: Optional timeout (not used in HTTP client, but kept for compatibility)
        
        Returns:
            Dictionary with "result" key containing the evaluation result
        """
        result = await self._call_tool("evaluate_js", {"expression": expression})
        
        if result.get("success"):
            return {"result": result.get("result")}
        else:
            return {"result": None, "error": result.get("error")}
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: Optional[float] = None) -> Any:
        """
        Call a tool by name (for compatibility with old interface)
        
        Maps old tool names to new tool names:
        - browser_navigate -> navigate
        - browser_take_screenshot -> screenshot
        - browser_snapshot -> dom_snapshot
        - browser_console_messages -> get_console
        - browser_evaluate -> evaluate_js
        - browser_click -> click
        - browser_type -> type
        - browser_wait -> wait_for
        - browser_wait_for -> wait_for
        - browser_get_url -> get_url
        - browser_dom_snapshot -> dom_snapshot
        """
        # Map old tool names to new ones
        tool_map = {
            "browser_navigate": "navigate",
            "browser_take_screenshot": "screenshot",
            "browser_snapshot": "dom_snapshot",
            "browser_console_messages": "get_console",
            "browser_evaluate": "evaluate_js",
            "browser_click": "click",
            "browser_type": "type",
            "browser_wait": "wait_for",
            "browser_wait_for": "wait_for",
            "browser_get_url": "get_url",
            "browser_dom_snapshot": "dom_snapshot",
            "browser_resize": "set_viewport",
            "browser_set_viewport": "set_viewport",
            "set_viewport_size": "set_viewport",
            "browser_start_recording": "start_recording",
            "browser_stop_recording": "stop_recording",
        }
        
        new_tool = tool_map.get(tool_name, tool_name)
        
        # Handle special cases
        if new_tool == "screenshot" and "filename" in arguments:
            arguments["path"] = arguments.pop("filename")
            if "fullPage" in arguments:
                arguments.pop("fullPage")  # Always full page
        
        if new_tool == "wait_for" and "duration" in arguments:
            # Convert browser_wait duration to timeout_ms
            arguments["timeout_ms"] = arguments.pop("duration")
        
        if new_tool == "start_recording" and "videoPath" in arguments:
            # Convert videoPath to video_path
            arguments["video_path"] = arguments.pop("videoPath")
        
        if new_tool == "get_console":
            result = await self.get_console(timeout=timeout)
            return {"messages": result}
        
        if new_tool == "dom_snapshot":
            result = await self._call_tool(new_tool, arguments)
            if result.get("success"):
                # Return in old format
                return {
                    "title": result.get("title", ""),
                    "textContent": result.get("visible_text_snippet", ""),
                    "buttons": [
                        el.get("text", "") for el in result.get("interactive_elements", [])
                        if el.get("tag") == "button"
                    ],
                    "interactive_elements": result.get("interactive_elements", []),
                }
            else:
                return {"success": False, "error": result.get("error")}
        
        # For other tools, call directly
        return await self._call_tool(new_tool, arguments)
    
    async def start_recording(self, video_path: str) -> bool:
        """
        Start video recording
        
        Args:
            video_path: Path where video will be saved (e.g., "recording.webm")
        
        Returns:
            True if successful, False otherwise
        """
        result = await self._call_tool("start_recording", {"video_path": video_path})
        return result.get("success", False)
    
    async def stop_recording(self) -> Optional[str]:
        """
        Stop video recording and return video path
        
        Returns:
            Path to saved video file, or None if recording failed
        """
        result = await self._call_tool("stop_recording", {})
        if result.get("success"):
            video_result = result.get("result", {})
            if isinstance(video_result, dict):
                return video_result.get("video_path")
            return result.get("video_path")
        return None
    
    async def close(self):
        """Close the client session"""
        if self._in_process:
            if self._browser_session:
                await self._browser_session.close()
        else:
            if self._session and not self._session.closed:
                await self._session.close()
    
    # New methods for direct access
    async def set_viewport(self, width: int, height: int) -> bool:
        """Set viewport size"""
        result = await self._call_tool("set_viewport", {"width": width, "height": height})
        return result.get("success", False)
    
    async def click(self, selector: str) -> bool:
        """Click an element"""
        result = await self._call_tool("click", {"selector": selector})
        return result.get("success", False)
    
    async def type_text(self, selector: str, text: str) -> bool:
        """Type text into an input"""
        result = await self._call_tool("type", {"selector": selector, "text": text})
        return result.get("success", False)
    
    async def wait_for(self, selector: Optional[str] = None, text: Optional[str] = None, timeout_ms: int = 30000) -> bool:
        """Wait for selector or text"""
        result = await self._call_tool("wait_for", {
            "selector": selector,
            "text": text,
            "timeout_ms": timeout_ms
        })
        return result.get("success", False)
    
    async def get_url(self) -> str:
        """Get current URL"""
        result = await self._call_tool("get_url", {})
        if result.get("success"):
            return result.get("result", "")
        return ""
    
    async def interactive_elements(self, max_interactive: int = 50) -> List[InteractiveElement]:
        """Get interactive elements"""
        result = await self._call_tool("interactive_elements", {"max_interactive": max_interactive})
        if result.get("success"):
            elements = result.get("result", [])
            return [InteractiveElement(**el) for el in elements]
        return []
