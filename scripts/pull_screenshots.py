#!/usr/bin/env python3
"""
Pull screenshots and videos from RunPod job output

Usage:
    python scripts/pull_screenshots.py <job_id> [--endpoint-id ENDPOINT_ID] [--api-key API_KEY] [--output-dir OUTPUT_DIR]
"""

import requests
import json
import base64
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

def pull_screenshots_from_job(
    job_id: str,
    endpoint_id: str,
    api_key: str,
    output_dir: Optional[Path] = None
):
    """Pull screenshots and videos from RunPod job"""
    
    if output_dir is None:
        output_dir = Path.cwd() / "screenshots" / job_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Pulling artifacts from job: {job_id}")
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
        return
    
    result = response.json()
    output = result.get('output', {})
    
    if result.get('status') != 'COMPLETED':
        print(f"⚠️  Job status: {result.get('status')}")
        print(f"   Job may still be running or failed")
        return
    
    print(f"✅ Job completed")
    
    # Extract screenshots from iterations_data
    iterations_data = output.get('iterations_data', [])
    if isinstance(iterations_data, str):
        try:
            import ast
            iterations_data = ast.literal_eval(iterations_data)
        except:
            iterations_data = []
    
    screenshot_count = 0
    video_count = 0
    
    print(f"\n📸 Extracting screenshots from {len(iterations_data)} iterations...")
    
    for i, iter_data in enumerate(iterations_data, 1):
        if not isinstance(iter_data, dict):
            continue
        
        iter_dir = output_dir / f"iter_{i}"
        iter_dir.mkdir(exist_ok=True)
        
        # Extract screenshots
        screenshots = iter_data.get('screenshots', {})
        if isinstance(screenshots, dict):
            for view_type, b64_data in screenshots.items():
                if b64_data:
                    try:
                        # Decode base64
                        image_data = base64.b64decode(b64_data)
                        screenshot_path = iter_dir / f"{view_type}.png"
                        screenshot_path.write_bytes(image_data)
                        screenshot_count += 1
                        print(f"   ✅ Saved: iter_{i}/{view_type}.png")
                    except Exception as e:
                        print(f"   ⚠️  Failed to decode {view_type}: {e}")
    
    # Check for video paths in artifacts
    artifacts = output.get('artifacts', {})
    if isinstance(artifacts, str):
        try:
            import ast
            artifacts = ast.literal_eval(artifacts)
        except:
            artifacts = {}
    
    videos = output.get('videos', [])
    if videos:
        print(f"\n🎥 Found {len(videos)} video references")
        print(f"   Note: Videos are stored on RunPod volume and cannot be downloaded via API")
        print(f"   Video paths:")
        for video_path in videos:
            print(f"      - {video_path}")
    
    print(f"\n✅ Extraction complete!")
    print(f"   Screenshots saved: {screenshot_count}")
    print(f"   Videos referenced: {len(videos) if videos else 0}")
    print(f"   Output directory: {output_dir}")
    
    # Create index HTML to view screenshots
    create_viewer_html(output_dir, iterations_data)
    
    return output_dir

def create_viewer_html(output_dir: Path, iterations_data: list):
    """Create HTML viewer for screenshots"""
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Screenshot Viewer</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .iteration {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .iteration h2 {
            margin-top: 0;
            color: #667eea;
        }
        .screenshots {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }
        .screenshot {
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }
        .screenshot img {
            width: 100%;
            height: auto;
            display: block;
        }
        .screenshot-label {
            padding: 0.5rem;
            background: #f8f8f8;
            font-size: 0.875rem;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>📸 Screenshot Viewer</h1>
"""
    
    for i, iter_data in enumerate(iterations_data, 1):
        if not isinstance(iter_data, dict):
            continue
        
        html_content += f"""
    <div class="iteration">
        <h2>Iteration {i}</h2>
        <div class="screenshots">
"""
        
        screenshots = iter_data.get('screenshots', {})
        if isinstance(screenshots, dict):
            for view_type, b64_data in screenshots.items():
                if b64_data:
                    html_content += f"""
            <div class="screenshot">
                <img src="data:image/png;base64,{b64_data}" alt="{view_type}">
                <div class="screenshot-label">{view_type}</div>
            </div>
"""
        
        html_content += """
        </div>
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    viewer_path = output_dir / "viewer.html"
    viewer_path.write_text(html_content)
    print(f"   📄 Viewer created: {viewer_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull screenshots from RunPod job")
    parser.add_argument("job_id", help="RunPod job ID")
    parser.add_argument("--endpoint-id", default="54fgxfa24iwxmq", help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"), help="RunPod API key")
    parser.add_argument("--output-dir", type=Path, help="Output directory for screenshots")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: RUNPOD_API_KEY not set. Provide via --api-key or environment variable")
        sys.exit(1)
    
    pull_screenshots_from_job(
        job_id=args.job_id,
        endpoint_id=args.endpoint_id,
        api_key=args.api_key,
        output_dir=args.output_dir
    )
