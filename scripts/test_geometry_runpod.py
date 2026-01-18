#!/usr/bin/env python3
"""
Send a test job to RunPod with geometry notes
"""

import os
import sys
import json
import requests
from pathlib import Path

# Default endpoint ID (can be overridden)
DEFAULT_ENDPOINT_ID = "54fgxfa24iwxmq"

def read_geometry_notes():
    """Read all geometry notes files and combine them"""
    # Get geometry notes directory (parent of GeminiLoop)
    script_dir = Path(__file__).parent.parent.parent
    geometry_dir = script_dir / "geometry_mock_notes"
    
    notes_files = [
        geometry_dir / "circles.md",
        geometry_dir / "coordinate_geometry.txt",
        geometry_dir / "practice_problems.md"
    ]
    
    combined_notes = ""
    for notes_file in notes_files:
        if notes_file.exists():
            with open(notes_file, 'r', encoding='utf-8') as f:
                combined_notes += f.read() + "\n\n"
        else:
            print(f"⚠️  Warning: {notes_file} not found")
    
    if not combined_notes:
        raise FileNotFoundError(f"Could not find geometry notes in {geometry_dir}")
    
    return combined_notes.strip()

def send_test_job(endpoint_id: str, api_key: str, notes: str, max_iterations: int = 2):
    """Send test job to RunPod"""
    
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    
    payload = {
        "input": {
            "task": "Create an interactive geometry course",
            "notes": notes,  # Custom notes bypass planner
            "max_iterations": max_iterations,
            "github_token": os.getenv("GITHUB_TOKEN", ""),
            "github_repo": os.getenv("GITHUB_REPO", "Yknld/geminiloopreults"),
            "base_branch": os.getenv("BASE_BRANCH", "main"),
            "enable_live_view": False
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"🚀 Sending test job to RunPod endpoint: {endpoint_id}")
    print(f"📝 Notes length: {len(notes)} characters")
    print(f"🔄 Max iterations: {max_iterations}")
    print(f"🌐 URL: {url}\n")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        print("✅ Job submitted successfully!")
        print(f"📋 Job ID: {result.get('id', 'N/A')}")
        print(f"📊 Status: {result.get('status', 'N/A')}")
        
        if result.get('status') == 'IN_QUEUE':
            print("\n⏳ Job is queued. Monitor progress at:")
            print(f"   https://www.runpod.io/console/serverless/{endpoint_id}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        sys.exit(1)

def main():
    """Main function"""
    # Get API key
    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        print("❌ Error: RUNPOD_API_KEY not set")
        print("   Set it with: export RUNPOD_API_KEY='your_key'")
        sys.exit(1)
    
    # Get endpoint ID (from env or default)
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", DEFAULT_ENDPOINT_ID)
    
    # Read geometry notes
    try:
        notes = read_geometry_notes()
        print(f"✅ Loaded geometry notes ({len(notes)} chars)\n")
    except Exception as e:
        print(f"❌ Error reading geometry notes: {e}")
        sys.exit(1)
    
    # Get max iterations from command line or default
    max_iterations = 2
    if len(sys.argv) > 1:
        try:
            max_iterations = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Invalid max_iterations: {sys.argv[1]}, using default: {max_iterations}")
    
    # Send job
    result = send_test_job(endpoint_id, api_key, notes, max_iterations)
    
    # Print job info
    print("\n" + "="*70)
    print("📋 Job Details:")
    print("="*70)
    print(json.dumps(result, indent=2))
    print("\n💡 Tip: Use the job ID to check status or pull artifacts:")
    print(f"   python scripts/list_jobs.py --endpoint-id {endpoint_id}")

if __name__ == "__main__":
    main()
