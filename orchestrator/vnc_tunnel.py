"""
VNC Tunnel Manager
Exposes the browser session via ngrok for live viewing
"""
import os
import subprocess
import time
import logging
from typing import Optional
from pyngrok import ngrok, conf

logger = logging.getLogger(__name__)


class VNCTunnel:
    """Manages VNC server and ngrok tunnel for live browser viewing"""
    
    def __init__(self, display: str = ":99", vnc_port: int = 5900):
        self.display = display
        self.vnc_port = vnc_port
        self.xvfb_process = None
        self.x11vnc_process = None
        self.tunnel = None
        self.ngrok_url = None
        
    def start(self) -> Optional[str]:
        """
        Start VNC server and ngrok tunnel
        Returns the ngrok URL for viewing
        """
        try:
            # 1. Start Xvfb (virtual display)
            logger.info(f"Starting Xvfb on display {self.display}...")
            self.xvfb_process = subprocess.Popen(
                ["Xvfb", self.display, "-screen", "0", "1920x1080x24", "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)  # Wait for Xvfb to start
            
            # Set DISPLAY environment variable
            os.environ['DISPLAY'] = self.display
            logger.info(f"✅ Xvfb started on {self.display}")
            
            # 2. Start x11vnc (VNC server)
            logger.info(f"Starting x11vnc on port {self.vnc_port}...")
            self.x11vnc_process = subprocess.Popen(
                [
                    "x11vnc",
                    "-display", self.display,
                    "-rfbport", str(self.vnc_port),
                    "-shared",
                    "-forever",
                    "-nopw",  # No password for simplicity
                    "-quiet"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)  # Wait for x11vnc to start
            logger.info(f"✅ x11vnc started on port {self.vnc_port}")
            
            # 3. Start ngrok tunnel
            logger.info("Starting ngrok tunnel...")
            
            # Set ngrok auth token from env if available
            ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
            if ngrok_token:
                conf.get_default().auth_token = ngrok_token
            
            # Create TCP tunnel to VNC port
            self.tunnel = ngrok.connect(self.vnc_port, "tcp")
            self.ngrok_url = self.tunnel.public_url
            
            logger.info(f"✅ ngrok tunnel created: {self.ngrok_url}")
            logger.info(f"   Connect with VNC viewer to watch live!")
            
            # Also log the web URL (ngrok has a web interface)
            tunnels = ngrok.get_tunnels()
            for tunnel in tunnels:
                if tunnel.proto == "tcp":
                    logger.info(f"   VNC URL: {tunnel.public_url}")
            
            return self.ngrok_url
            
        except Exception as e:
            logger.error(f"Failed to start VNC tunnel: {e}")
            self.stop()
            return None
    
    def stop(self):
        """Stop VNC server and ngrok tunnel"""
        logger.info("Stopping VNC tunnel...")
        
        # Close ngrok tunnel
        if self.tunnel:
            try:
                ngrok.disconnect(self.tunnel.public_url)
                logger.info("✅ ngrok tunnel closed")
            except:
                pass
        
        # Stop x11vnc
        if self.x11vnc_process:
            try:
                self.x11vnc_process.terminate()
                self.x11vnc_process.wait(timeout=5)
                logger.info("✅ x11vnc stopped")
            except:
                self.x11vnc_process.kill()
        
        # Stop Xvfb
        if self.xvfb_process:
            try:
                self.xvfb_process.terminate()
                self.xvfb_process.wait(timeout=5)
                logger.info("✅ Xvfb stopped")
            except:
                self.xvfb_process.kill()
    
    def get_url(self) -> Optional[str]:
        """Get the ngrok URL for viewing"""
        return self.ngrok_url
