"""
Browser session management using Playwright

Manages a persistent browser session with Playwright, providing
all browser automation capabilities needed for QA evaluation.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from pathlib import Path
import base64

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .types import (
    SimpleResponse,
    SnapshotResponse,
    InteractiveElement,
    BoundingBox,
    ConsoleMessage,
)

logger = logging.getLogger(__name__)


def _compute_selector(page: Page, element) -> str:
    """
    Compute a stable selector for an element.
    
    Priority order:
    1. #id
    2. [data-testid]
    3. [aria-label]
    4. [name]
    5. CSS path with nth-of-type
    """
    # This will be called from evaluate, so we need to pass element info
    # For now, we'll compute it in Python after getting element info
    pass


async def _compute_selector_async(page: Page, element_handle) -> str:
    """
    Compute a stable selector for an element using Playwright.
    
    Priority order:
    1. #id
    2. [data-testid]
    3. [aria-label]
    4. [name]
    5. CSS path with nth-of-type
    """
    try:
        # Try ID first
        element_id = await element_handle.get_attribute("id")
        if element_id:
            return f"#{element_id}"
        
        # Try data-testid
        test_id = await element_handle.get_attribute("data-testid")
        if test_id:
            return f'[data-testid="{test_id}"]'
        
        # Try aria-label
        aria_label = await element_handle.get_attribute("aria-label")
        if aria_label:
            return f'[aria-label="{aria_label}"]'
        
        # Try name
        name = await element_handle.get_attribute("name")
        if name:
            tag = await element_handle.evaluate("(e) => e.tagName.toLowerCase()")
            return f'{tag}[name="{name}"]'
        
        # Fallback: compute CSS path
        # This is a simplified version - in production you might want a more robust path
        tag = await element_handle.evaluate("(e) => e.tagName.toLowerCase()")
        parent = await element_handle.evaluate_handle("(e) => e.parentElement")
        if parent:
            siblings = await parent.evaluate(f"(p) => Array.from(p.children).filter(c => c.tagName.toLowerCase() === '{tag}')")
            index = await element_handle.evaluate("(e) => Array.from(e.parentElement.children).indexOf(e)")
            if index is not None and index >= 0:
                return f"{tag}:nth-of-type({index + 1})"
        
        # Last resort: tag name
        return tag
    except Exception as e:
        logger.warning(f"Failed to compute selector: {e}")
        return "unknown"


class BrowserSession:
    """Manages a persistent browser session with Playwright"""
    
    def __init__(self, headless: bool = True, viewport: Tuple[int, int] = (1440, 900)):
        self.headless = headless
        self.viewport = viewport
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.console_messages: List[ConsoleMessage] = []
        self._initialized = False
        self._recording = False
        self._video_path: Optional[str] = None
    
    async def start(self):
        """Start the browser session"""
        if self._initialized:
            return
        
        logger.info(f"Starting browser session (headless={self.headless}, viewport={self.viewport})")
        
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={"width": self.viewport[0], "height": self.viewport[1]},
        )
        
        self.page = await self.context.new_page()
        
        # Wire console and error listeners
        self._wire_listeners()
        
        self._initialized = True
        logger.info("Browser session started")
    
    def _wire_listeners(self):
        """Wire up console and error listeners"""
        if not self.page:
            return
        
        def on_console(msg):
            level = msg.type
            text = msg.text
            self.console_messages.append(ConsoleMessage(
                level=level,
                text=text,
                timestamp=None  # Could add timestamp if needed
            ))
            # Keep only last 1000 messages
            if len(self.console_messages) > 1000:
                self.console_messages.pop(0)
        
        def on_pageerror(error):
            self.console_messages.append(ConsoleMessage(
                level="error",
                text=str(error),
                timestamp=None
            ))
            # Keep only last 1000 messages
            if len(self.console_messages) > 1000:
                self.console_messages.pop(0)
        
        self.page.on("console", on_console)
        self.page.on("pageerror", on_pageerror)
    
    async def navigate(self, url: str) -> SimpleResponse:
        """Navigate to a URL"""
        try:
            if not self.page:
                await self.start()
            
            logger.info(f"Navigating to: {url}")
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            
            title = await self.page.title()
            logger.info(f"Loaded: {title}")
            
            return SimpleResponse(success=True, result={"title": title, "url": self.page.url})
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def set_viewport(self, width: int, height: int) -> SimpleResponse:
        """Set viewport size"""
        try:
            if not self.page:
                await self.start()
            
            logger.info(f"Setting viewport: {width}x{height}")
            await self.page.set_viewport_size({"width": width, "height": height})
            self.viewport = (width, height)
            
            return SimpleResponse(success=True)
        except Exception as e:
            logger.error(f"Set viewport failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def screenshot(self, path: Optional[str] = None, return_base64: bool = False) -> SimpleResponse:
        """Take a screenshot"""
        try:
            if not self.page:
                await self.start()
            
            logger.info(f"Taking screenshot: {path or 'base64'}")
            
            # Wait for page to stabilize
            try:
                await self.page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass  # Continue even if networkidle times out
            
            screenshot_bytes = await self.page.screenshot(
                path=path,
                full_page=True,
                timeout=30000,
                animations="disabled"
            )
            
            if return_base64:
                if isinstance(screenshot_bytes, bytes):
                    base64_str = base64.b64encode(screenshot_bytes).decode()
                    return SimpleResponse(success=True, result={"base64": base64_str, "path": path})
                else:
                    # If path was provided, read the file
                    if path:
                        with open(path, "rb") as f:
                            base64_str = base64.b64encode(f.read()).decode()
                        return SimpleResponse(success=True, result={"base64": base64_str, "path": path})
            
            return SimpleResponse(success=True, result={"path": path})
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def dom_snapshot(self, max_interactive: int = 50) -> SnapshotResponse:
        """Get DOM snapshot with interactive elements"""
        try:
            if not self.page:
                await self.start()
            
            logger.info("Getting DOM snapshot...")
            
            url = self.page.url
            title = await self.page.title()
            
            # Get visible text snippet
            try:
                text = await self.page.inner_text("body")
                snippet = text[:1500] if text else ""
            except:
                snippet = ""
            
            # Count elements
            count_buttons = len(await self.page.query_selector_all("button"))
            count_inputs = len(await self.page.query_selector_all("input"))
            count_links = len(await self.page.query_selector_all("a"))
            
            # Get interactive elements
            interactive_elements = []
            selectors = "button, [role='button'], a, input, select, textarea, [onclick], [tabindex]"
            elements = await self.page.query_selector_all(selectors)
            
            for i, el in enumerate(elements[:max_interactive]):
                try:
                    tag = await el.evaluate("(e) => e.tagName.toLowerCase()")
                    text_content = await el.inner_text()
                    visible = await el.is_visible()
                    disabled = await el.get_attribute("disabled") is not None
                    
                    bbox_dict = await el.bounding_box()
                    if bbox_dict:
                        bbox = BoundingBox(
                            x=int(bbox_dict["x"]),
                            y=int(bbox_dict["y"]),
                            width=int(bbox_dict["width"]),
                            height=int(bbox_dict["height"])
                        )
                    else:
                        bbox = BoundingBox(x=0, y=0, width=0, height=0)
                    
                    # Compute stable selector
                    selector = await _compute_selector_async(self.page, el)
                    
                    role = await el.get_attribute("role")
                    element_type = tag
                    
                    interactive_elements.append(InteractiveElement(
                        selector=selector,
                        text=text_content.strip()[:200],  # Limit text length
                        role=role,
                        tag=tag,
                        visible=visible,
                        bbox=bbox,
                        disabled=disabled,
                        type=element_type
                    ))
                except Exception as e:
                    logger.debug(f"Failed to process element {i}: {e}")
                    continue
            
            # Get console messages (copy current buffer)
            console = self.console_messages.copy()
            
            logger.info(f"Snapshot: {len(interactive_elements)} interactive elements, {len(console)} console messages")
            
            return SnapshotResponse(
                success=True,
                url=url,
                title=title,
                visible_text_snippet=snippet,
                count_buttons=count_buttons,
                count_inputs=count_inputs,
                count_links=count_links,
                a11y_tree=None,  # Could add a11y tree if needed
                interactive_elements=interactive_elements,
                console=console,
                error=None
            )
        except Exception as e:
            logger.error(f"DOM snapshot failed: {e}")
            return SnapshotResponse(
                success=False,
                error=str(e),
                url=None,
                title=None,
                visible_text_snippet=None,
                count_buttons=0,
                count_inputs=0,
                count_links=0,
                a11y_tree=None,
                interactive_elements=[],
                console=[]
            )
    
    async def click(self, selector: str) -> SimpleResponse:
        """Click an element by selector"""
        try:
            if not self.page:
                await self.start()
            
            logger.info(f"Clicking: {selector}")
            await self.page.click(selector, timeout=10000)
            
            return SimpleResponse(success=True, message=f"Clicked {selector}")
        except Exception as e:
            logger.warning(f"Click failed: {e}")
            return SimpleResponse(success=False, error=str(e), message=f"Failed to click {selector}")
    
    async def type(self, selector: str, text: str) -> SimpleResponse:
        """Type text into an input field"""
        try:
            if not self.page:
                await self.start()
            
            logger.info(f"Typing into {selector}: {text[:50]}...")
            await self.page.fill(selector, text, timeout=10000)
            
            return SimpleResponse(success=True, message=f"Typed into {selector}")
        except Exception as e:
            logger.warning(f"Type failed: {e}")
            return SimpleResponse(success=False, error=str(e), message=f"Failed to type into {selector}")
    
    async def wait_for(self, selector: Optional[str] = None, text: Optional[str] = None, timeout_ms: int = 30000) -> SimpleResponse:
        """Wait for selector or text to appear"""
        try:
            if not self.page:
                await self.start()
            
            timeout_seconds = timeout_ms / 1000.0
            
            if selector:
                logger.info(f"Waiting for selector: {selector}")
                await self.page.wait_for_selector(selector, timeout=timeout_seconds * 1000)
            elif text:
                logger.info(f"Waiting for text: {text}")
                await self.page.wait_for_function(
                    f"() => document.body && document.body.innerText.includes({repr(text)})",
                    timeout=timeout_seconds * 1000
                )
            else:
                # Just wait for timeout
                await asyncio.sleep(timeout_seconds)
            
            return SimpleResponse(success=True, message=f"Wait complete")
        except Exception as e:
            logger.warning(f"Wait failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def get_url(self) -> SimpleResponse:
        """Get current URL"""
        try:
            if not self.page:
                await self.start()
            
            url = self.page.url
            return SimpleResponse(success=True, result=url)
        except Exception as e:
            logger.error(f"Get URL failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def evaluate_js(self, expression: str) -> SimpleResponse:
        """Evaluate JavaScript expression"""
        try:
            if not self.page:
                await self.start()
            
            logger.debug(f"Evaluating JS: {expression[:100]}...")
            result = await self.page.evaluate(expression)
            
            return SimpleResponse(success=True, result=result)
        except Exception as e:
            logger.warning(f"JS evaluation failed: {e}")
            return SimpleResponse(success=False, error=str(e), result=None)
    
    async def get_console(self) -> List[ConsoleMessage]:
        """Get console messages"""
        return self.console_messages.copy()
    
    async def start_recording(self, video_path: str) -> SimpleResponse:
        """Start video recording"""
        try:
            logger.info(f"Starting video recording: {video_path}")
            
            # Ensure video directory exists
            video_dir = Path(video_path).parent
            video_dir.mkdir(parents=True, exist_ok=True)
            
            # Close current context if recording (to finalize previous video)
            if self._recording and self.context:
                try:
                    await self.context.close()
                except:
                    pass
            
            # Create new context with video recording
            if not self.browser:
                await self.start()
            
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                record_video_dir=str(video_dir),
                record_video_size={"width": self.viewport[0], "height": self.viewport[1]}
            )
            
            self.page = await self.context.new_page()
            
            # Wire listeners for new page
            self._wire_listeners()
            
            self._video_path = video_path
            self._recording = True
            
            logger.info("Video recording started")
            return SimpleResponse(success=True, result={"video_path": video_path})
        except Exception as e:
            logger.error(f"Start recording failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def stop_recording(self) -> SimpleResponse:
        """Stop video recording and save to file"""
        try:
            if not self._recording or not self.context:
                return SimpleResponse(success=False, error="No recording in progress")
            
            logger.info("Stopping video recording...")
            
            # Close context to finalize video
            await self.context.close()
            
            # Playwright saves video with a hash, we need to find it
            video_dir = Path(self._video_path).parent
            video_file = None
            
            if video_dir.exists():
                # Find most recent .webm file
                webm_files = list(video_dir.glob("*.webm"))
                if webm_files:
                    # Sort by modification time, get most recent
                    webm_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    video_file = webm_files[0]
                    
                    # Rename to desired path if different
                    target_path = Path(self._video_path)
                    if video_file != target_path:
                        if target_path.exists():
                            target_path.unlink()  # Remove existing file
                        video_file.rename(target_path)
                        video_file = target_path
            
            # Create new context without recording for continued use
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]}
            )
            self.page = await self.context.new_page()
            self._wire_listeners()
            
            self._recording = False
            final_path = str(video_file) if video_file else self._video_path
            
            logger.info(f"Video recording stopped: {final_path}")
            return SimpleResponse(success=True, result={"video_path": final_path})
        except Exception as e:
            logger.error(f"Stop recording failed: {e}")
            return SimpleResponse(success=False, error=str(e))
    
    async def close(self) -> SimpleResponse:
        """Close the browser session"""
        try:
            logger.info("Closing browser session...")
            
            # Stop recording if active
            if self._recording:
                try:
                    await self.stop_recording()
                except:
                    pass
            
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            self._initialized = False
            self._recording = False
            logger.info("Browser session closed")
            
            return SimpleResponse(success=True)
        except Exception as e:
            logger.error(f"Close failed: {e}")
            return SimpleResponse(success=False, error=str(e))
