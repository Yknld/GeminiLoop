"""
MCP Server for BrowserUse

Exposes browser automation tools via FastAPI HTTP interface.
Can be run standalone or integrated into existing MCP infrastructure.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .browser_session import BrowserSession
from .types import SimpleResponse, SnapshotResponse

logger = logging.getLogger(__name__)

# Global browser session
browser_session: Optional[BrowserSession] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage browser session lifecycle"""
    global browser_session
    
    # Startup
    logger.info("Starting BrowserUse MCP server...")
    headless = True  # Default to headless for RunPod
    browser_session = BrowserSession(headless=headless)
    await browser_session.start()
    logger.info("BrowserUse MCP server ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BrowserUse MCP server...")
    if browser_session:
        await browser_session.close()
    logger.info("BrowserUse MCP server stopped")


app = FastAPI(
    title="BrowserUse MCP Server",
    description="MCP server for browser automation using Playwright",
    lifespan=lifespan
)


class ToolRequest(BaseModel):
    """Tool request model"""
    tool: str
    args: Optional[Dict[str, Any]] = None


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "browser_initialized": browser_session is not None and browser_session._initialized}


@app.post("/call_tool", response_model=Dict[str, Any])
async def call_tool(req: ToolRequest):
    """Call a browser tool"""
    global browser_session
    
    if not browser_session:
        raise HTTPException(status_code=503, detail="Browser session not initialized")
    
    tool = req.tool
    args = req.args or {}
    
    try:
        if tool == "navigate":
            url = args.get("url")
            if not url:
                raise ValueError("url is required")
            result = await browser_session.navigate(url)
            return result.model_dump()
        
        elif tool == "set_viewport":
            width = args.get("width")
            height = args.get("height")
            if width is None or height is None:
                raise ValueError("width and height are required")
            result = await browser_session.set_viewport(width, height)
            return result.model_dump()
        
        elif tool == "screenshot":
            path = args.get("path")
            return_base64 = args.get("return_base64", False)
            result = await browser_session.screenshot(path=path, return_base64=return_base64)
            return result.model_dump()
        
        elif tool == "dom_snapshot":
            max_interactive = args.get("max_interactive", 50)
            result = await browser_session.dom_snapshot(max_interactive=max_interactive)
            return result.model_dump()
        
        elif tool == "interactive_elements":
            # Return just interactive elements from snapshot
            snapshot = await browser_session.dom_snapshot(max_interactive=args.get("max_interactive", 50))
            if snapshot.success:
                return SimpleResponse(success=True, result=snapshot.interactive_elements).model_dump()
            else:
                return SimpleResponse(success=False, error=snapshot.error).model_dump()
        
        elif tool == "click":
            selector = args.get("selector")
            if not selector:
                raise ValueError("selector is required")
            result = await browser_session.click(selector)
            return result.model_dump()
        
        elif tool == "type":
            selector = args.get("selector")
            text = args.get("text")
            if not selector or text is None:
                raise ValueError("selector and text are required")
            result = await browser_session.type(selector, text)
            return result.model_dump()
        
        elif tool == "wait_for":
            selector = args.get("selector")
            text = args.get("text")
            timeout_ms = args.get("timeout_ms", 30000)
            result = await browser_session.wait_for(selector=selector, text=text, timeout_ms=timeout_ms)
            return result.model_dump()
        
        elif tool == "get_url":
            result = await browser_session.get_url()
            return result.model_dump()
        
        elif tool == "evaluate_js":
            expression = args.get("expression")
            if not expression:
                raise ValueError("expression is required")
            result = await browser_session.evaluate_js(expression)
            return result.model_dump()
        
        elif tool == "get_console":
            messages = await browser_session.get_console()
            return SimpleResponse(success=True, result=[msg.model_dump() for msg in messages]).model_dump()
        
        elif tool == "start_recording":
            video_path = args.get("video_path") or args.get("videoPath")
            if not video_path:
                raise ValueError("video_path is required")
            result = await browser_session.start_recording(video_path)
            return result.model_dump()
        
        elif tool == "stop_recording":
            result = await browser_session.stop_recording()
            return result.model_dump()
        
        elif tool == "close":
            result = await browser_session.close()
            return result.model_dump()
        
        else:
            return SimpleResponse(success=False, error=f"Unknown tool: {tool}").model_dump()
    
    except Exception as e:
        logger.error(f"Tool call failed: {tool} - {e}")
        return SimpleResponse(success=False, error=str(e)).model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
