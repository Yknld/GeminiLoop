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
from pathlib import Path
from typing import Dict, Any

# Import orchestrator
from orchestrator.main import run_loop
from orchestrator.run_state import RunConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler
    
    Expected input:
    {
        "input": {
            "task": "Create a landing page",
            "max_iterations": 2,
            "github_token": "optional",
            "github_repo": "optional",
            "base_branch": "optional"
        }
    }
    
    Returns:
    {
        "output": {
            "run_id": "...",
            "status": "completed",
            "final_score": 85,
            "final_passed": true,
            "preview_url": "...",
            "report": {...},
            "manifest": {...},
            "screenshots": ["url1", "url2"],
            "github_branch_url": "..." (if enabled)
        }
    }
    """
    
    try:
        logger.info("🚀 GeminiLoop Serverless Handler Started")
        logger.info(f"Event: {json.dumps(event, indent=2)}")
        
        # Extract input
        input_data = event.get("input", {})
        task = input_data.get("task")
        
        if not task:
            return {
                "error": "Missing required field: task",
                "status": "error"
            }
        
        # Extract optional parameters
        max_iterations = input_data.get("max_iterations", 2)
        
        # Set GitHub env vars if provided
        if "github_token" in input_data:
            os.environ["GITHUB_TOKEN"] = input_data["github_token"]
        if "github_repo" in input_data:
            os.environ["GITHUB_REPO"] = input_data["github_repo"]
        if "base_branch" in input_data:
            os.environ["BASE_BRANCH"] = input_data["base_branch"]
        
        # Set other optional env vars
        if "openhands_mode" in input_data:
            os.environ["OPENHANDS_MODE"] = input_data["openhands_mode"]
        
        # Run orchestrator
        logger.info(f"Running orchestrator for task: {task}")
        
        state = asyncio.run(run_loop(
            task=task,
            max_iterations=max_iterations,
            base_dir=Path("/runpod-volume/runs")  # Use persistent volume
        ))
        
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
        
        # Include report data
        if state.result.iterations:
            response["iterations_data"] = []
            for iter_result in state.result.iterations:
                response["iterations_data"].append({
                    "iteration": iter_result.iteration,
                    "score": iter_result.score,
                    "passed": iter_result.passed,
                    "feedback": iter_result.feedback[:200] if iter_result.feedback else ""
                })
        
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
        
        logger.info(f"✅ Run complete: {state.result.run_id}")
        logger.info(f"   Score: {state.result.final_score}/100")
        logger.info(f"   Status: {state.result.status}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Handler error: {e}")
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "error"
        }


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


if __name__ == "__main__":
    # Test locally
    test_handler()
