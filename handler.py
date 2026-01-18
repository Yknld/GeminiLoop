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
                # Use state.result.artifacts_dir if available, otherwise construct path (note: double "runs" in path)
                if state.result.artifacts_dir:
                    artifacts_base = Path(state.result.artifacts_dir)
                else:
                    # Fallback: construct path with double "runs" (base_dir/runs/run_id)
                    artifacts_base = Path(f"/runpod-volume/runs/runs/{state.result.run_id}/artifacts")
                
                screenshots_dir = artifacts_base / f"screenshots/iter_{iter_result.iteration}"
                logger.info(f"Looking for screenshots in: {screenshots_dir}")
                logger.info(f"Directory exists: {screenshots_dir.exists()}")
                
                if screenshots_dir.exists():
                    # Collect all screenshots (agentic evaluator saves step_X_phase.png files)
                    screenshot_files = list(screenshots_dir.rglob("*.png"))
                    logger.info(f"Found {len(screenshot_files)} PNG files in {screenshots_dir}")
                    
                    if screenshot_files:
                        for screenshot_file in screenshot_files:
                            try:
                                # Use relative filename as key (e.g., "step_1_before.png")
                                rel_name = screenshot_file.name
                                encoded = _encode_image_base64(screenshot_file)
                                if encoded:
                                    iter_data["screenshots"][rel_name] = encoded
                                    logger.info(f"✅ Encoded screenshot: {rel_name}")
                                else:
                                    logger.warning(f"⚠️  Failed to encode {screenshot_file}")
                            except Exception as e:
                                logger.warning(f"⚠️  Failed to encode screenshot {screenshot_file}: {e}")
                    else:
                        logger.warning(f"⚠️  No PNG files found in {screenshots_dir}")
                        # List what's actually in the directory
                        try:
                            actual_files = list(screenshots_dir.iterdir())
                            logger.warning(f"   Directory contains: {[f.name for f in actual_files]}")
                        except Exception as e:
                            logger.warning(f"   Could not list directory: {e}")
                    
                    # Also check for legacy desktop/mobile screenshots
                    desktop_path = screenshots_dir / "desktop.png"
                    if desktop_path.exists() and "desktop" not in iter_data["screenshots"]:
                        iter_data["screenshots"]["desktop"] = _encode_image_base64(desktop_path)
                        logger.info("✅ Added legacy desktop.png")
                    
                    mobile_path = screenshots_dir / "mobile.png"
                    if mobile_path.exists() and "mobile" not in iter_data["screenshots"]:
                        iter_data["screenshots"]["mobile"] = _encode_image_base64(mobile_path)
                        logger.info("✅ Added legacy mobile.png")
                else:
                    logger.warning(f"⚠️  Screenshots directory does not exist: {screenshots_dir}")
                
                logger.info(f"Iteration {iter_result.iteration}: Collected {len(iter_data['screenshots'])} screenshots")
                
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
        # Use state.result.artifacts_dir if available, otherwise construct path (note: double "runs" in path)
        if state.result.artifacts_dir:
            artifacts_base = Path(state.result.artifacts_dir)
        else:
            # Fallback: construct path with double "runs" (base_dir/runs/run_id)
            artifacts_base = Path(f"/runpod-volume/runs/runs/{state.result.run_id}/artifacts")
        
        screenshots_dir = artifacts_base / "screenshots"
        if screenshots_dir.exists():
            screenshot_files = list(screenshots_dir.rglob("*.png"))
            # Store screenshot paths relative to /runpod-volume/runs (single "runs")
            # Path structure: /runpod-volume/runs/runs/{run_id}/artifacts/screenshots/...
            # We want: runs/{run_id}/artifacts/screenshots/...
            try:
                # Try relative to /runpod-volume/runs (single)
                base_path = Path("/runpod-volume/runs")
                response["screenshots"] = [str(f.relative_to(base_path)) for f in screenshot_files]
            except ValueError:
                # Fallback: use filename if relative calculation fails
                response["screenshots"] = [f.name for f in screenshot_files]
        
        # Get video paths and encode videos
        # Check multiple possible locations for videos
        artifacts_dir = artifacts_base
        video_files = []
        
        # Check screenshots directory (legacy location)
        screenshots_videos = artifacts_dir / "screenshots"
        if screenshots_videos.exists():
            video_files.extend(list(screenshots_videos.rglob("*.webm")))
        
        # Check artifacts root directory
        if artifacts_dir.exists():
            video_files.extend(list(artifacts_dir.rglob("*.webm")))
        
        # Check iteration-specific directories
        for iter_dir in artifacts_dir.glob("screenshots/iter_*"):
            if iter_dir.exists():
                video_files.extend(list(iter_dir.rglob("*.webm")))
        
        if video_files:
            # Remove duplicates
            video_files = list(set(video_files))
            # Store video paths relative to /runpod-volume/runs (single "runs")
            # Path structure: /runpod-volume/runs/runs/{run_id}/artifacts/screenshots/...
            # We want: runs/{run_id}/artifacts/screenshots/...
            try:
                # Try relative to /runpod-volume/runs (single)
                base_path = Path("/runpod-volume/runs")
                video_relative_paths = [str(f.relative_to(base_path)) for f in video_files]
            except ValueError:
                # Fallback: use filename if relative calculation fails
                video_relative_paths = [f.name for f in video_files]
            
            response["videos"] = video_relative_paths
            response["artifacts"]["videos"] = video_relative_paths
            
            logger.info(f"📹 Found {len(video_files)} video file(s)")
            
            # Encode videos as base64 for download
            response["videos_data"] = {}
            for video_file in video_files:
                try:
                    # Use filename as key for videos_data (simpler and more reliable)
                    video_filename = video_file.name
                    encoded_video = _encode_video_base64(video_file)
                    if encoded_video:
                        response["videos_data"][video_filename] = encoded_video
                        logger.info(f"✅ Encoded video: {video_filename} ({video_file.stat().st_size / (1024*1024):.1f}MB)")
                    else:
                        logger.warning(f"⚠️  Video too large or failed to encode: {video_filename}")
                except Exception as e:
                    logger.warning(f"⚠️  Error encoding video {video_file}: {e}")
        else:
            logger.info("📹 No video files found")
        
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
        # Use state.result.artifacts_dir if available, otherwise construct path (note: double "runs" in path)
        if state.result.artifacts_dir:
            artifacts_dir = Path(state.result.artifacts_dir)
        else:
            # Fallback: construct path with double "runs" (base_dir/runs/run_id)
            artifacts_dir = Path(f"/runpod-volume/runs/runs/{state.result.run_id}/artifacts")
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
