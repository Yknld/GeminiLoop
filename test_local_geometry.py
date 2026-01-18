#!/usr/bin/env python3
"""
Local test script for geometry notes
Runs the orchestrator locally without waiting for RunPod builds
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Set required environment variables
os.environ.setdefault("GOOGLE_AI_STUDIO_API_KEY", os.getenv("GOOGLE_AI_STUDIO_API_KEY", ""))
os.environ.setdefault("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
os.environ.setdefault("GITHUB_REPO", os.getenv("GITHUB_REPO", "Yknld/geminiloopreults"))
os.environ.setdefault("BASE_BRANCH", os.getenv("BASE_BRANCH", "main"))

# Read geometry notes
geometry_notes_path = Path(__file__).parent.parent / "geometry_mock_notes"
notes_files = [
    geometry_notes_path / "circles.md",
    geometry_notes_path / "coordinate_geometry.txt",
    geometry_notes_path / "practice_problems.md"
]

geometry_notes = ""
for notes_file in notes_files:
    if notes_file.exists():
        with open(notes_file, 'r') as f:
            geometry_notes += f.read() + "\n\n"

if not geometry_notes:
    print("❌ Error: Could not find geometry notes files")
    print(f"   Expected location: {geometry_notes_path}")
    sys.exit(1)

print("🚀 Starting local test with geometry notes...")
print(f"📝 Notes length: {len(geometry_notes)} characters")
print(f"📁 Notes from: {geometry_notes_path}\n")

# Import orchestrator
from orchestrator.main import run_loop

async def main():
    """Run the orchestrator loop locally"""
    try:
        # Run with geometry notes
        result = await run_loop(
            task="Create an interactive geometry course",
            max_iterations=2,  # Reduced for faster local testing
            custom_notes=geometry_notes
        )
        
        print("\n" + "="*70)
        print("✅ Test completed!")
        print("="*70)
        print(f"Run ID: {result.result.run_id}")
        print(f"Final Score: {result.result.final_score}")
        print(f"Status: {result.result.status}")
        if result.result.preview_url:
            print(f"Preview URL: {result.result.preview_url}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
