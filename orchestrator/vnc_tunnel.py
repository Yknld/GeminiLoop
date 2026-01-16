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
            logger.info("=" * 70)
            logger.info("🔴 STARTING VNC TUNNEL FOR LIVE BROWSER VIEWING")
            logger.info("=" * 70)
            
            # 1. Start Xvfb (virtual display)
            logger.info(f"Step 1/3: Starting Xvfb on display {self.display}...")
            try:
                self.xvfb_process = subprocess.Popen(
                    ["Xvfb", self.display, "-screen", "0", "1920x1080x24", "-ac"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                time.sleep(2)  # Wait for Xvfb to start
                
                # Check if Xvfb is running
                if self.xvfb_process.poll() is not None:
                    stderr = self.xvfb_process.stderr.read().decode()
                    raise Exception(f"Xvfb failed to start: {stderr}")
                
                # Set DISPLAY environment variable
                os.environ['DISPLAY'] = self.display
                logger.info(f"✅ Xvfb started successfully (PID: {self.xvfb_process.pid})")
            except Exception as e:
                logger.error(f"❌ Xvfb failed: {e}")
                raise
            
            # 2. Start x11vnc (VNC server)
            logger.info(f"Step 2/3: Starting x11vnc on port {self.vnc_port}...")
            try:
                self.x11vnc_process = subprocess.Popen(
                    [
                        "x11vnc",
                        "-display", self.display,
                        "-rfbport", str(self.vnc_port),
                        "-shared",
                        "-forever",
                        "-nopw",  # No password for simplicity
                        "-q"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                time.sleep(2)  # Wait for x11vnc to start
                
                # Check if x11vnc is running
                if self.x11vnc_process.poll() is not None:
                    stderr = self.x11vnc_process.stderr.read().decode()
                    raise Exception(f"x11vnc failed to start: {stderr}")
                
                logger.info(f"✅ x11vnc started successfully (PID: {self.x11vnc_process.pid})")
            except Exception as e:
                logger.error(f"❌ x11vnc failed: {e}")
                raise
            
            # 3. Start ngrok tunnel
            logger.info(f"Step 3/3: Starting ngrok tunnel...")
            
            # Set ngrok auth token from env if available
            ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
            if not ngrok_token:
                raise Exception("NGROK_AUTH_TOKEN not found in environment variables!")
            
            logger.info(f"   Using ngrok token: {ngrok_token[:10]}...")
            
            try:
                conf.get_default().auth_token = ngrok_token
                
                # Create TCP tunnel to VNC port
                logger.info(f"   Creating TCP tunnel to port {self.vnc_port}...")
                self.tunnel = ngrok.connect(self.vnc_port, "tcp")
                self.ngrok_url = self.tunnel.public_url
                
                logger.info("=" * 70)
                logger.info(f"✅ VNC TUNNEL ACTIVE!")
                logger.info(f"🔴 URL: {self.ngrok_url}")
                logger.info(f"📺 Connect with: open vnc://{self.ngrok_url.replace('tcp://', '')}")
                logger.info("=" * 70)
                
                # Also log all tunnels
                tunnels = ngrok.get_tunnels()
                logger.info(f"Active ngrok tunnels: {len(tunnels)}")
                for tunnel in tunnels:
                    logger.info(f"  - {tunnel.proto}: {tunnel.public_url}")
                
                return self.ngrok_url
                
            except Exception as e:
                logger.error(f"❌ ngrok tunnel failed: {e}")
                raise
            
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
