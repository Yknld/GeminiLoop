#!/usr/bin/env python3
"""
Manual test of agentic evaluator on local HTML file
"""

import asyncio
import sys
import os
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_agentic_evaluator():
    from orchestrator.agentic_evaluator import AgenticEvaluator
    from orchestrator.mcp_real_client import PlaywrightMCPClient
    
    # Set API key
    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY"):
        print("❌ Error: GOOGLE_AI_STUDIO_API_KEY not set")
        return
    
    # Initialize
    print("🚀 Starting agentic evaluator test")
    print("=" * 70)
    
    evaluator = AgenticEvaluator(max_exploration_steps=10)
    mcp_client = PlaywrightMCPClient()
    
    # Use the ML course module we just generated
    html_file = Path("/tmp/ml_course/modules/module-01-basics.html")
    if not html_file.exists():
        print(f"❌ File not found: {html_file}")
        return
    
    # Create artifacts dir
    artifacts_dir = Path("/tmp/agentic_test")
    artifacts_dir.mkdir(exist_ok=True)
    screenshots_dir = artifacts_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    try:
        # Start MCP
        print("🌐 Starting Playwright MCP...")
        await mcp_client.connect()
        print("✅ MCP connected")
        
        # Test URL
        url = f"file://{html_file.absolute()}"
        print(f"\n📄 Testing: {url}")
        
        task = "Interactive lesson teaching supervised vs unsupervised learning with visual patterns"
        
        # Run evaluation
        print("\n🤖 Running agentic evaluation...")
        print("=" * 70)
        
        result = await evaluator.evaluate_page(
            url=url,
            mcp_client=mcp_client,
            task=task,
            artifacts_dir=screenshots_dir
        )
        
        print("\n" + "=" * 70)
        print("📊 EVALUATION RESULTS")
        print("=" * 70)
        print(f"Score: {result.score}/100")
        print(f"Passed: {result.passed}")
        print(f"\nCategory Scores:")
        for category, score in result.category_scores.items():
            print(f"  {category}: {score}")
        
        print(f"\nFeedback: {result.feedback[:500]}...")
        
        # Check exploration log
        log_file = screenshots_dir / "agentic_exploration.json"
        if log_file.exists():
            import json
            with open(log_file) as f:
                log = json.load(f)
            print(f"\n📝 Exploration Log:")
            print(f"  Steps taken: {log['total_steps']}")
            print(f"  Completion: {log['completion_reason']}")
            print(f"\n  Actions:")
            for step in log['exploration_steps']:
                print(f"    Step {step['step']}: {step['tool']} - {step.get('args', {})}")
        
    finally:
        await mcp_client.disconnect()
        print("\n✅ Test complete")

if __name__ == "__main__":
    asyncio.run(test_agentic_evaluator())
