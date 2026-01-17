#!/usr/bin/env python3
"""
Pull video from RunPod job output

Usage:
    python scripts/pull_video.py <job_id> [--endpoint-id ENDPOINT_ID] [--api-key API_KEY] [--output-dir OUTPUT_DIR]
"""

import requests
import json
import os
import sys
import base64
from pathlib import Path
from typing import Dict, Any, Optional

def pull_video_from_job(
    job_id: str,
    endpoint_id: str,
    api_key: str,
    output_dir: Optional[Path] = None
):
    """Pull video from RunPod job output"""
    
    if output_dir is None:
        output_dir = Path.cwd() / "videos" / job_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📥 Pulling video from job: {job_id}")
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
    
    # Get videos_data (base64 encoded)
    videos_data = output.get('videos_data', {})
    if isinstance(videos_data, str):
        try:
            import ast
            videos_data = ast.literal_eval(videos_data)
        except:
            videos_data = {}
    
    video_count = 0
    
    if videos_data:
        print(f"\n🎥 Extracting {len(videos_data)} video(s)...")
        
        for video_path, base64_data in videos_data.items():
            try:
                # Extract base64 data (remove data URI prefix if present)
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                
                # Decode base64
                video_data = base64.b64decode(base64_data)
                
                # Get filename from path
                filename = Path(video_path).name
                if not filename.endswith('.webm'):
                    filename = f"{filename}.webm"
                
                video_file = output_dir / filename
                video_file.write_bytes(video_data)
                
                video_count += 1
                size_mb = len(video_data) / (1024 * 1024)
                print(f"   ✅ Saved: {filename} ({size_mb:.1f}MB)")
            except Exception as e:
                print(f"   ⚠️  Failed to decode video {video_path}: {e}")
    else:
        print(f"\n⚠️  No videos_data in output")
        print(f"   Videos may not have been encoded or job didn't record videos")
        
        # Check for video paths
        videos = output.get('videos', [])
        if videos:
            print(f"   Video paths found (but not encoded):")
            for video in videos:
                print(f"      - {video}")
    
    print(f"\n✅ Extraction complete!")
    print(f"   Videos saved: {video_count}")
    print(f"   Output directory: {output_dir}")
    
    return output_dir

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull video from RunPod job")
    parser.add_argument("job_id", help="RunPod job ID")
    parser.add_argument("--endpoint-id", default="54fgxfa24iwxmq", help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"), help="RunPod API key")
    parser.add_argument("--output-dir", type=Path, help="Output directory for video")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: RUNPOD_API_KEY not set. Provide via --api-key or environment variable")
        sys.exit(1)
    
    pull_video_from_job(
        job_id=args.job_id,
        endpoint_id=args.endpoint_id,
        api_key=args.api_key,
        output_dir=args.output_dir
    )
