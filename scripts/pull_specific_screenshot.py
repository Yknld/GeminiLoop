#!/usr/bin/env python3
"""
Pull a specific screenshot from RunPod job output

Usage:
    python scripts/pull_specific_screenshot.py <job_id> <screenshot_name> [--endpoint-id ENDPOINT_ID] [--api-key API_KEY] [--output-dir OUTPUT_DIR]

Example:
    python scripts/pull_specific_screenshot.py abc123 step_1_after.png
"""

import requests
import json
import base64
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

def pull_specific_screenshot(
    job_id: str,
    screenshot_name: str,
    endpoint_id: str,
    api_key: str,
    output_dir: Optional[Path] = None
):
    """Pull a specific screenshot from RunPod job"""
    
    if output_dir is None:
        output_dir = Path.cwd() / "screenshots" / job_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Pulling screenshot '{screenshot_name}' from job: {job_id}")
    print(f"📁 Output directory: {output_dir}")
    
    # Get job status
    url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    print(f"\n🔍 Fetching job status...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(f"   {response.text}")
        return None
    
    result = response.json()
    output = result.get('output', {})
    
    if result.get('status') != 'COMPLETED':
        print(f"⚠️  Job status: {result.get('status')}")
        print(f"   Job may still be running or failed")
        return None
    
    print(f"✅ Job completed")
    
    # Extract screenshots from iterations_data
    iterations_data = output.get('iterations_data', [])
    if isinstance(iterations_data, str):
        try:
            import ast
            iterations_data = ast.literal_eval(iterations_data)
        except:
            iterations_data = []
    
    print(f"\n📸 Searching for '{screenshot_name}' in {len(iterations_data)} iterations...")
    
    found = False
    for i, iter_data in enumerate(iterations_data, 1):
        if not isinstance(iter_data, dict):
            continue
        
        # Extract screenshots
        screenshots = iter_data.get('screenshots', {})
        if isinstance(screenshots, dict):
            # Check if the screenshot name matches (exact or partial)
            for view_type, b64_data in screenshots.items():
                if screenshot_name in view_type or view_type == screenshot_name:
                    if b64_data:
                        try:
                            # Decode base64
                            image_data = base64.b64decode(b64_data)
                            screenshot_path = output_dir / screenshot_name
                            screenshot_path.write_bytes(image_data)
                            print(f"   ✅ Saved: {screenshot_path}")
                            found = True
                            return screenshot_path
                        except Exception as e:
                            print(f"   ⚠️  Failed to decode {view_type}: {e}")
    
    if not found:
        print(f"   ❌ Screenshot '{screenshot_name}' not found in job output")
        print(f"   Available screenshots:")
        for i, iter_data in enumerate(iterations_data, 1):
            if isinstance(iter_data, dict):
                screenshots = iter_data.get('screenshots', {})
                if isinstance(screenshots, dict):
                    for view_type in screenshots.keys():
                        print(f"      - {view_type}")
        return None
    
    return output_dir

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull specific screenshot from RunPod job")
    parser.add_argument("job_id", help="RunPod job ID")
    parser.add_argument("screenshot_name", help="Screenshot name (e.g., 'step_1_after.png')")
    parser.add_argument("--endpoint-id", default="54fgxfa24iwxmq", help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"), help="RunPod API key")
    parser.add_argument("--output-dir", type=Path, help="Output directory for screenshot")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: RUNPOD_API_KEY not set. Provide via --api-key or environment variable")
        sys.exit(1)
    
    pull_specific_screenshot(
        job_id=args.job_id,
        screenshot_name=args.screenshot_name,
        endpoint_id=args.endpoint_id,
        api_key=args.api_key,
        output_dir=args.output_dir
    )
