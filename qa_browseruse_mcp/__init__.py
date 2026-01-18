"""
BrowserUse MCP - Browser automation layer using Playwright

Provides a clean MCP interface for browser automation that replaces
the brittle Gemini-controlled browser QA setup.
"""

from .client import BrowserUseMCPClient
from .types import (
    SimpleResponse,
    SnapshotResponse,
    InteractiveElement,
    BoundingBox,
    ConsoleMessage,
)

__all__ = [
    "BrowserUseMCPClient",
    "SimpleResponse",
    "SnapshotResponse",
    "InteractiveElement",
    "BoundingBox",
    "ConsoleMessage",
]
