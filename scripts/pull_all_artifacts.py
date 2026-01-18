#!/usr/bin/env python3
"""
Pull ALL artifacts from RunPod job: HTML files, screenshots, videos, planner output, etc.

Usage:
    python scripts/pull_all_artifacts.py <job_id> [--endpoint-id ENDPOINT_ID] [--api-key API_KEY] [--output-dir OUTPUT_DIR]
"""

import requests
import json
import base64
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

def pull_all_artifacts(
    job_id: str,
    endpoint_id: str,
    api_key: str,
    output_dir: Optional[Path] = None
):
    """Pull all artifacts from RunPod job"""
    
    if output_dir is None:
        output_dir = Path.cwd() / "job_artifacts" / job_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Pulling ALL artifacts from job: {job_id}")
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
    
    # Save full output JSON
    full_output_path = output_dir / "full_output.json"
    full_output_path.write_text(json.dumps(result, indent=2))
    print(f"\n💾 Saved full output: {full_output_path}")
    
    # Extract HTML files
    print(f"\n📄 Extracting HTML files...")
    html_count = 0
    
    # Check generated_files
    generated_files = output.get('generated_files', {})
    if isinstance(generated_files, dict):
        for filename, content in generated_files.items():
            if content:
                try:
                    if isinstance(content, str):
                        html_data = content
                    else:
                        html_data = str(content)
                    
                    html_path = output_dir / filename
                    html_path.write_text(html_data, encoding='utf-8')
                    html_count += 1
                    print(f"   ✅ Saved: {filename} ({len(html_data)} chars)")
                except Exception as e:
                    print(f"   ⚠️  Failed to save {filename}: {e}")
    
    # Also check files (legacy)
    html_files = output.get('files', {})
    if isinstance(html_files, dict):
        for filename, content in html_files.items():
            if content:
                try:
                    # Decode if base64
                    if isinstance(content, str) and content.startswith('data:'):
                        # Extract base64 part
                        b64_data = content.split(',')[1]
                        html_data = base64.b64decode(b64_data).decode('utf-8')
                    elif isinstance(content, str):
                        html_data = content
                    else:
                        html_data = str(content)
                    
                    html_path = output_dir / filename
                    html_path.write_text(html_data, encoding='utf-8')
                    html_count += 1
                    print(f"   ✅ Saved: {filename} ({len(html_data)} chars)")
                except Exception as e:
                    print(f"   ⚠️  Failed to save {filename}: {e}")
    
    # Extract screenshots from iterations_data
    iterations_data = output.get('iterations_data', [])
    if isinstance(iterations_data, str):
        try:
            import ast
            iterations_data = ast.literal_eval(iterations_data)
        except:
            iterations_data = []
    
    screenshot_count = 0
    
    print(f"\n📸 Extracting screenshots from {len(iterations_data)} iterations...")
    screenshots_dir = output_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    for i, iter_data in enumerate(iterations_data, 1):
        if not isinstance(iter_data, dict):
            continue
        
        iter_dir = screenshots_dir / f"iter_{i}"
        iter_dir.mkdir(exist_ok=True)
        
        # Extract screenshots
        screenshots = iter_data.get('screenshots', {})
        if isinstance(screenshots, dict):
            for filename, b64_data in screenshots.items():
                if b64_data:
                    try:
                        # Decode base64
                        image_data = base64.b64decode(b64_data)
                        screenshot_path = iter_dir / f"{filename}"
                        if not screenshot_path.suffix:
                            screenshot_path = iter_dir / f"{filename}.png"
                        screenshot_path.write_bytes(image_data)
                        screenshot_count += 1
                        print(f"   ✅ Saved: iter_{i}/{screenshot_path.name}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to decode {filename}: {e}")
    
    # Extract videos
    print(f"\n🎥 Extracting videos...")
    videos_data = output.get('videos_data', {})
    if isinstance(videos_data, str):
        try:
            import ast
            videos_data = ast.literal_eval(videos_data)
        except:
            videos_data = {}
    
    video_count = 0
    videos_dir = output_dir / "videos"
    videos_dir.mkdir(exist_ok=True)
    
    if videos_data:
        for filename, b64_data in videos_data.items():
            if b64_data:
                try:
                    video_data = base64.b64decode(b64_data)
                    video_path = videos_dir / filename
                    video_path.write_bytes(video_data)
                    video_count += 1
                    print(f"   ✅ Saved: {filename} ({len(video_data) / 1024 / 1024:.2f} MB)")
                except Exception as e:
                    print(f"   ⚠️  Failed to decode {filename}: {e}")
    
    # Extract planner output
    print(f"\n📋 Extracting planner output...")
    planner_dir = output_dir / "planner_output"
    planner_dir.mkdir(exist_ok=True)
    
    planner_files = {
        'planner_prompt.txt': output.get('planner_prompt'),
        'planner_output.json': output.get('planner_output'),
        'course_plan.json': output.get('course_plan'),
        'planner_thinking.txt': output.get('planner_thinking'),
    }
    
    planner_count = 0
    for filename, content in planner_files.items():
        if content:
            try:
                if isinstance(content, str):
                    # Try to parse as JSON first
                    try:
                        json_data = json.loads(content)
                        planner_path = planner_dir / filename
                        planner_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
                    except:
                        # Not JSON, save as text
                        planner_path = planner_dir / filename
                        planner_path.write_text(content, encoding='utf-8')
                elif isinstance(content, dict):
                    planner_path = planner_dir / filename
                    planner_path.write_text(json.dumps(content, indent=2), encoding='utf-8')
                else:
                    planner_path = planner_dir / filename
                    planner_path.write_text(str(content), encoding='utf-8')
                
                planner_count += 1
                print(f"   ✅ Saved: {filename}")
            except Exception as e:
                print(f"   ⚠️  Failed to save {filename}: {e}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"✅ Extraction complete!")
    print(f"{'='*70}")
    print(f"   📄 HTML files: {html_count}")
    print(f"   📸 Screenshots: {screenshot_count}")
    print(f"   🎥 Videos: {video_count}")
    print(f"   📋 Planner files: {planner_count}")
    print(f"   📁 Output directory: {output_dir}")
    print(f"{'='*70}")
    
    # Create index HTML to view everything
    create_index_html(output_dir, html_files, iterations_data, videos_data)
    
    return output_dir

def create_index_html(output_dir: Path, html_files: dict, iterations_data: list, videos_data: dict):
    """Create HTML index to view all artifacts"""
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Artifacts Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
            background: #f5f5f5;
            line-height: 1.6;
        }
        h1 {
            color: #333;
            margin-bottom: 2rem;
        }
        .section {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            margin-bottom: 1rem;
            color: #667eea;
        }
        .file-list {
            list-style: none;
        }
        .file-list li {
            padding: 0.5rem;
            border-bottom: 1px solid #eee;
        }
        .file-list li:last-child {
            border-bottom: none;
        }
        .file-list a {
            color: #667eea;
            text-decoration: none;
        }
        .file-list a:hover {
            text-decoration: underline;
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
        .video-list {
            list-style: none;
        }
        .video-list li {
            padding: 0.5rem;
            border-bottom: 1px solid #eee;
        }
        .video-list video {
            max-width: 100%;
            margin-top: 0.5rem;
        }
    </style>
</head>
<body>
    <h1>📦 Job Artifacts Viewer</h1>
"""
    
    # HTML Files Section
    if html_files:
        html_content += """
    <div class="section">
        <h2>📄 Generated HTML Files</h2>
        <ul class="file-list">
"""
        for filename in html_files.keys():
            html_content += f'            <li><a href="{filename}" target="_blank">{filename}</a></li>\n'
        html_content += "        </ul>\n    </div>\n"
    
    # Screenshots Section
    if iterations_data:
        html_content += """
    <div class="section">
        <h2>📸 Screenshots</h2>
"""
        for i, iter_data in enumerate(iterations_data, 1):
            if not isinstance(iter_data, dict):
                continue
            
            html_content += f"""
        <h3>Iteration {i}</h3>
        <div class="screenshots">
"""
            screenshots = iter_data.get('screenshots', {})
            if isinstance(screenshots, dict):
                for filename, b64_data in screenshots.items():
                    if b64_data:
                        html_content += f"""
            <div class="screenshot">
                <img src="data:image/png;base64,{b64_data}" alt="{filename}">
                <div class="screenshot-label">{filename}</div>
            </div>
"""
            html_content += """
        </div>
"""
        html_content += "    </div>\n"
    
    # Videos Section
    if videos_data:
        html_content += """
    <div class="section">
        <h2>🎥 Videos</h2>
        <ul class="video-list">
"""
        for filename, b64_data in videos_data.items():
            if b64_data:
                html_content += f"""
            <li>
                <strong>{filename}</strong>
                <video controls>
                    <source src="data:video/webm;base64,{b64_data}" type="video/webm">
                    Your browser does not support the video tag.
                </video>
            </li>
"""
        html_content += "        </ul>\n    </div>\n"
    
    # Planner Output Section
    html_content += """
    <div class="section">
        <h2>📋 Planner Output</h2>
        <ul class="file-list">
            <li><a href="planner_output/planner_prompt.txt" target="_blank">planner_prompt.txt</a></li>
            <li><a href="planner_output/planner_output.json" target="_blank">planner_output.json</a></li>
            <li><a href="planner_output/course_plan.json" target="_blank">course_plan.json</a></li>
            <li><a href="planner_output/planner_thinking.txt" target="_blank">planner_thinking.txt</a></li>
        </ul>
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    index_path = output_dir / "index.html"
    index_path.write_text(html_content)
    print(f"   📄 Index viewer created: {index_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull all artifacts from RunPod job")
    parser.add_argument("job_id", help="RunPod job ID")
    parser.add_argument("--endpoint-id", default="54fgxfa24iwxmq", help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"), help="RunPod API key")
    parser.add_argument("--output-dir", type=Path, help="Output directory for artifacts")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: RUNPOD_API_KEY not set. Provide via --api-key or environment variable")
        sys.exit(1)
    
    pull_all_artifacts(
        job_id=args.job_id,
        endpoint_id=args.endpoint_id,
        api_key=args.api_key,
        output_dir=args.output_dir
    )
