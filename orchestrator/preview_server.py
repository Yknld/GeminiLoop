"""
HTTP Preview Server

Serves files from PROJECT_ROOT via HTTP instead of file:// URLs.
This is required because file:// navigation is blocked in many contexts.
"""

import os
import logging
import asyncio
import signal
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional

logger = logging.getLogger(__name__)


class PreviewHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves files from a specific directory"""
    
    def __init__(self, *args, directory: Optional[str] = None, **kwargs):
        # Store directory before calling parent __init__
        self.serve_directory = directory
        super().__init__(*args, directory=directory, **kwargs)
    
    def log_message(self, format, *args):
        """Override to use Python logging instead of stderr"""
        logger.debug(f"Preview server: {format % args}")
    
    def end_headers(self):
        """Add CORS headers for browser compatibility"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.end_headers()


class PreviewServer:
    """
    Lightweight HTTP server for serving project files
    
    Replaces file:// URLs with proper HTTP serving.
    Runs in a background thread to avoid blocking the main loop.
    """
    
    def __init__(self, serve_dir: Path, host: str = "127.0.0.1", port: int = 8000):
        self.serve_dir = Path(serve_dir)
        self.host = host
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self._running = False
        
        logger.info(f"Preview server configured:")
        logger.info(f"  Directory: {self.serve_dir}")
        logger.info(f"  URL: http://{self.host}:{self.port}/")
    
    def start(self):
        """Start the preview server in a background thread"""
        
        if self._running:
            logger.warning("Preview server already running")
            return
        
        # Ensure serve directory exists
        self.serve_dir.mkdir(parents=True, exist_ok=True)
        
        # Create handler with specific directory
        def handler(*args, **kwargs):
            return PreviewHandler(*args, directory=str(self.serve_dir), **kwargs)
        
        try:
            # Create HTTP server
            self.httpd = HTTPServer((self.host, self.port), handler)
            
            # Start in background thread
            self.thread = Thread(target=self._serve, daemon=True)
            self.thread.start()
            
            self._running = True
            
            logger.info(f"✅ Preview server started on http://{self.host}:{self.port}/")
            logger.info(f"   Serving: {self.serve_dir}")
            
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(f"⚠️  Port {self.port} already in use, server may already be running")
                self._running = True  # Assume it's our server
            else:
                logger.error(f"❌ Failed to start preview server: {e}")
                raise
    
    def _serve(self):
        """Internal method to serve HTTP requests"""
        try:
            logger.info(f"Preview server thread started")
            self.httpd.serve_forever()
        except Exception as e:
            logger.error(f"Preview server error: {e}")
        finally:
            logger.info("Preview server thread stopped")
    
    def stop(self):
        """Stop the preview server"""
        
        if not self._running:
            return
        
        logger.info("Stopping preview server...")
        
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self._running = False
        logger.info("✅ Preview server stopped")
    
    @property
    def url(self) -> str:
        """Get the preview server URL"""
        return f"http://{self.host}:{self.port}/"
    
    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._running
    
    def get_file_url(self, filename: str) -> str:
        """Get URL for a specific file"""
        return f"{self.url}{filename}"


# Global server instance
_preview_server: Optional[PreviewServer] = None


def get_preview_server(serve_dir: Optional[Path] = None, host: str = "127.0.0.1", port: int = 8000) -> PreviewServer:
    """
    Get the global preview server singleton
    
    Args:
        serve_dir: Directory to serve (required on first call)
        host: Server host (default: 127.0.0.1)
        port: Server port (default: 8000)
    
    Returns:
        PreviewServer instance
    """
    global _preview_server
    
    if _preview_server is None:
        if serve_dir is None:
            raise ValueError("serve_dir is required when creating preview server for the first time")
        
        _preview_server = PreviewServer(serve_dir, host, port)
        _preview_server.start()
    
    return _preview_server


def stop_preview_server():
    """Stop the global preview server"""
    global _preview_server
    
    if _preview_server:
        _preview_server.stop()
        _preview_server = None


def reset_preview_server():
    """Reset the global preview server (for testing)"""
    stop_preview_server()


# Cleanup on exit
import atexit
atexit.register(stop_preview_server)
