#!/usr/bin/env python3
"""
List recent RunPod jobs

Usage:
    python scripts/list_jobs.py [--endpoint-id ENDPOINT_ID] [--api-key API_KEY] [--limit LIMIT]
"""

import requests
import json
import os
import sys
from typing import Optional

def list_recent_jobs(
    endpoint_id: str,
    api_key: str,
    limit: int = 10
):
    """List recent RunPod jobs"""
    
    print(f"📋 Listing recent jobs for endpoint: {endpoint_id}")
    
    # RunPod doesn't have a direct "list jobs" endpoint for serverless
    # We need to check the RunPod dashboard or use webhooks
    # For now, we'll try to get job info if we have a job ID
    
    print("\n⚠️  RunPod Serverless API doesn't have a direct 'list jobs' endpoint.")
    print("   You need to provide the job ID (UUID) from:")
    print("   1. RunPod dashboard (https://www.runpod.io/console/serverless)")
    print("   2. The response when you submitted the job")
    print("   3. Webhook notifications (if configured)")
    print("\n   Job IDs are UUIDs like: 'abc123-def456-...'")
    print("   Run IDs (like '20260118_043404_3b5a78ae') are internal and different.")
    
    return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="List recent RunPod jobs")
    parser.add_argument("--endpoint-id", default="54fgxfa24iwxmq", help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv("RUNPOD_API_KEY"), help="RunPod API key")
    parser.add_argument("--limit", type=int, default=10, help="Number of jobs to list")
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: RUNPOD_API_KEY not set. Provide via --api-key or environment variable")
        sys.exit(1)
    
    list_recent_jobs(
        endpoint_id=args.endpoint_id,
        api_key=args.api_key,
        limit=args.limit
    )
