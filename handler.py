#!/usr/bin/env python3
"""
RunPod Serverless Handler for GeminiLoop

Handles incoming requests from RunPod serverless infrastructure.
Runs the orchestrator and returns results.
"""

import asyncio
import os
import json
import logging
import traceback
import base64
from pathlib import Path
from typing import Dict, Any, Optional

# Import runpod first (required for serverless)
try:
    import runpod
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    logger.info("✅ RunPod handler starting...")
except Exception as e:
    print(f"❌ Failed to import runpod: {e}")
    raise

# Import VNC tunnel for live browser viewing
from orchestrator.vnc_tunnel import VNCTunnel


def _encode_image_base64(image_path: Path) -> str:
    """Encode image to base64 data URI"""
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return None

def _encode_video_base64(video_path: Path, max_size_mb: int = 50) -> Optional[str]:
    """Encode video to base64 data URI (with size limit to avoid huge responses)"""
    try:
        # Check file size
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            logger.warning(f"Video {video_path} is too large ({file_size_mb:.1f}MB > {max_size_mb}MB), skipping encoding")
            return None
        
        with open(video_path, 'rb') as f:
            video_data = f.read()
            base64_data = base64.b64encode(video_data).decode('utf-8')
            logger.info(f"✅ Encoded video: {video_path.name} ({file_size_mb:.1f}MB)")
            return f"data:video/webm;base64,{base64_data}"
    except Exception as e:
        logger.warning(f"Failed to encode video {video_path}: {e}")
        return None


async def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler
    
    Expected input (job["input"]):
    {
        "task": "Create a landing page",
        "notes": "Optional: Custom prompt/notes to use instead of planner-generated prompt",
        "max_iterations": 2,
        "github_token": "optional",
        "github_repo": "optional",
        "base_branch": "optional",
        "enable_live_view": false  # Enable ngrok tunnel for live browser viewing
    }
    
    Returns:
    {
        "run_id": "...",
        "status": "completed",
        "final_score": 85,
        "final_passed": true,
        "preview_url": "...",
        "live_view_url": "vnc://...",  # If enabled
        "report": {...},
        "manifest": {...},
        "screenshots": ["url1", "url2"],
        "github_branch_url": "..." (if enabled)
    }
    """
    
    try:
        logger.info("🚀 GeminiLoop Serverless Handler Started")
        logger.info(f"Job: {json.dumps(job, indent=2)}")
        
        # Import orchestrator here (after container is healthy)
        try:
            from orchestrator.main import run_loop
            logger.info("✅ Orchestrator imported")
        except Exception as e:
            logger.error(f"❌ Failed to import orchestrator: {e}")
            return {
                "error": f"Failed to import orchestrator: {str(e)}",
                "traceback": traceback.format_exc(),
                "status": "error"
            }
        
        # Extract input from job
        input_data = job.get("input", {})
        task = input_data.get("task", "")
        custom_notes = input_data.get("notes")  # Custom prompt/notes (optional)
        
        # If notes provided, task is optional (use notes as prompt)
        # If no notes, task is required
        if not custom_notes and not task:
            return {
                "error": "Missing required field: either 'task' or 'notes' must be provided",
                "status": "error"
            }
        
        # If only notes provided, use a placeholder task
        if custom_notes and not task:
            task = "Custom notes provided"
        
        # Extract optional parameters
        max_iterations = input_data.get("max_iterations", 10)  # Increased default to 10
        
        # Set GitHub env vars if provided
        if "github_token" in input_data:
            os.environ["GITHUB_TOKEN"] = input_data["github_token"]
        if "github_repo" in input_data:
            os.environ["GITHUB_REPO"] = input_data["github_repo"]
        if "base_branch" in input_data:
            os.environ["BASE_BRANCH"] = input_data["base_branch"]
        
        # Start VNC tunnel if enabled (for live browser viewing)
        vnc_tunnel = None
        live_view_url = None
        enable_live_view = input_data.get("enable_live_view", False)
        
        if enable_live_view:
            logger.info("🔴 Starting VNC tunnel for live browser viewing...")
            vnc_tunnel = VNCTunnel()
            live_view_url = vnc_tunnel.start()
            
            if live_view_url:
                logger.info(f"✅ Live view available at: {live_view_url}")
                logger.info(f"   Connect with any VNC viewer to watch the browser live!")
            else:
                logger.warning("⚠️  Failed to start VNC tunnel, continuing without live view")
        
        # Set other optional env vars
        if "openhands_mode" in input_data:
            os.environ["OPENHANDS_MODE"] = input_data["openhands_mode"]
        
        # Run orchestrator
        logger.info(f"Running orchestrator for task: {task}")
        if custom_notes:
            logger.info(f"Using custom notes/prompt ({len(custom_notes)} chars)")
        
        state = await run_loop(
            task=task,
            max_iterations=max_iterations,
            base_dir=Path("/runpod-volume/runs"),  # Use persistent volume
            custom_notes=custom_notes  # Pass custom notes if provided
        )
        
        # Build response
        response = {
            "run_id": state.result.run_id,
            "status": state.result.status,
            "task": state.result.task,
            "final_score": state.result.final_score,
            "final_passed": state.result.final_passed,
            "iterations": state.result.current_iteration,
            "duration_seconds": state.result.total_duration_seconds,
            "preview_url": state.result.preview_url,
        }
        
        # Add GitHub info if available
        if hasattr(state.result, 'github_branch_url') and state.result.github_branch_url:
            response["github_branch"] = state.result.github_branch
            response["github_branch_url"] = state.result.github_branch_url
        
        # Include report data with screenshots
        if state.result.iterations:
            response["iterations_data"] = []
            for iter_result in state.result.iterations:
                iter_data = {
                    "iteration": iter_result.iteration,
                    "score": iter_result.score,
                    "passed": iter_result.passed,
                    "feedback": iter_result.feedback[:200] if iter_result.feedback else "",
                    "screenshots": {}
                }
                
                # Add screenshots for this iteration
                screenshots_dir = Path(f"/runpod-volume/runs/{state.result.run_id}/artifacts/screenshots/iter_{iter_result.iteration}")
                if screenshots_dir.exists():
                    # Desktop screenshot
                    desktop_path = screenshots_dir / "desktop.png"
                    if desktop_path.exists():
                        iter_data["screenshots"]["desktop"] = _encode_image_base64(desktop_path)
                    
                    # Mobile screenshot
                    mobile_path = screenshots_dir / "mobile.png"
                    if mobile_path.exists():
                        iter_data["screenshots"]["mobile"] = _encode_image_base64(mobile_path)
                
                response["iterations_data"].append(iter_data)
        
        # Add manifest if available
        if hasattr(state, 'manifest'):
            response["manifest"] = state.manifest.to_dict()
        
        # Add artifact paths (relative for download)
        response["artifacts"] = {
            "report": f"runs/{state.result.run_id}/artifacts/report.json",
            "manifest": f"runs/{state.result.run_id}/artifacts/manifest.json",
            "view": f"runs/{state.result.run_id}/artifacts/view.html",
            "trace": f"runs/{state.result.run_id}/artifacts/trace.jsonl"
        }
        
        # Get screenshot paths
        screenshots_dir = Path(f"/runpod-volume/runs/{state.result.run_id}/artifacts/screenshots")
        if screenshots_dir.exists():
            screenshot_files = list(screenshots_dir.rglob("*.png"))
            response["screenshots"] = [str(f.relative_to("/runpod-volume/runs")) for f in screenshot_files]
        
        # Get video paths and encode videos
        videos_dir = Path(f"/runpod-volume/runs/{state.result.run_id}/artifacts/screenshots")
        if videos_dir.exists():
            video_files = list(videos_dir.rglob("*.webm"))
            if video_files:
                response["videos"] = [str(f.relative_to("/runpod-volume/runs")) for f in video_files]
                response["artifacts"]["videos"] = [str(f.relative_to("/runpod-volume/runs")) for f in video_files]
                
                # Encode videos as base64 for download
                response["videos_data"] = {}
                for video_file in video_files:
                    try:
                        relative_path = str(video_file.relative_to("/runpod-volume/runs"))
                        encoded_video = _encode_video_base64(video_file)
                        if encoded_video:
                            response["videos_data"][relative_path] = encoded_video
                            logger.info(f"✅ Encoded video: {relative_path} ({video_file.stat().st_size / (1024*1024):.1f}MB)")
                        else:
                            logger.warning(f"⚠️  Video too large or failed to encode: {relative_path}")
                    except Exception as e:
                        logger.warning(f"⚠️  Error encoding video {video_file}: {e}")
        
        # Add generated file contents
        response["generated_files"] = {}
        site_dir = state.site_dir
        if site_dir.exists():
            for file in site_dir.rglob("*"):
                if file.is_file() and file.suffix in [".html", ".css", ".js"]:
                    try:
                        relative_path = str(file.relative_to(site_dir))
                        response["generated_files"][relative_path] = file.read_text()
                    except:
                        pass
        
        # Add planner output to response
        artifacts_dir = Path(f"/runpod-volume/runs/{state.result.run_id}/artifacts")
        planner_files = {
            "openhands_prompt.txt": "planner_prompt",
            "planner_output.json": "planner_output",
            "course_plan.json": "course_plan",
            "planner_thinking.txt": "planner_thinking"
        }
        
        response["planner_output"] = {}
        for filename, key in planner_files.items():
            planner_file = artifacts_dir / filename
            if planner_file.exists():
                try:
                    if filename.endswith('.json'):
                        response["planner_output"][key] = json.loads(planner_file.read_text())
                    else:
                        response["planner_output"][key] = planner_file.read_text()
                    logger.info(f"✅ Included planner output: {filename}")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to read planner file {filename}: {e}")
        
        logger.info(f"✅ Run complete: {state.result.run_id}")
        logger.info(f"   Score: {state.result.final_score}/100")
        logger.info(f"   Status: {state.result.status}")
        logger.info(f"   Generated files: {list(response['generated_files'].keys())}")
        
        # Add live view URL if enabled
        if live_view_url:
            response["live_view_url"] = live_view_url
            logger.info(f"🔴 Live view: {live_view_url}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Handler error: {e}")
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "error"
        }
    
    finally:
        # Stop VNC tunnel if it was started
        if 'vnc_tunnel' in locals() and vnc_tunnel:
            logger.info("🛑 Stopping VNC tunnel...")
            vnc_tunnel.stop()


def test_handler():
    """Test handler locally"""
    test_event = {
        "input": {
            "task": "Create a simple hello world page",
            "max_iterations": 2
        }
    }
    
    result = handler(test_event)
    print(json.dumps(result, indent=2))


def test_handler_with_custom_notes():
    """Test handler with custom notes"""
    test_event = {
        "input": {
            "task": "Create a calculator",
            "notes": "Create a fully functional calculator with:\n- Basic operations (+, -, *, /)\n- Clear button\n- Modern UI design\n- All in a single HTML file",
            "max_iterations": 2
        }
    }
    
    result = handler(test_event)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    # Start RunPod serverless handler
    runpod.serverless.start({"handler": handler})
