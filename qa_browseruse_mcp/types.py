"""
Type definitions for BrowserUse MCP
"""

from pydantic import BaseModel
from typing import Optional, List, Any, Dict


class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x: int
    y: int
    width: int
    height: int


class InteractiveElement(BaseModel):
    """Interactive element information"""
    selector: str
    text: str
    role: Optional[str] = None
    tag: str
    visible: bool
    bbox: BoundingBox
    disabled: bool
    type: Optional[str] = None  # e.g., "button", "link", "input"


class ConsoleMessage(BaseModel):
    """Console message"""
    level: str  # "error", "warning", "info", "log", etc.
    text: str
    timestamp: Optional[int] = None


class SnapshotResponse(BaseModel):
    """DOM snapshot response"""
    success: bool
    url: Optional[str] = None
    title: Optional[str] = None
    visible_text_snippet: Optional[str] = None
    count_buttons: int = 0
    count_inputs: int = 0
    count_links: int = 0
    a11y_tree: Optional[Any] = None
    interactive_elements: List[InteractiveElement] = []
    console: List[ConsoleMessage] = []
    error: Optional[str] = None


class SimpleResponse(BaseModel):
    """Simple success/error response"""
    success: bool
    error: Optional[str] = None
    result: Optional[Any] = None
    message: Optional[str] = None
