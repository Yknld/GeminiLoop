#!/usr/bin/env python3
"""
Test the improved agentic evaluator with all new features:
- Multimodal vision
- Before/after verification
- Dialog detection
- Stable selectors
- New tools (wait_for, hover, press_key, etc.)
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_improved_evaluator():
    from orchestrator.agentic_evaluator import AgenticEvaluator
    from orchestrator.mcp_real_client import PlaywrightMCPClient
    
    # Check API key
    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY"):
        print("❌ Error: GOOGLE_AI_STUDIO_API_KEY not set")
        print("   Set it with: export GOOGLE_AI_STUDIO_API_KEY='your-key'")
        return
    
    print("🚀 Testing Improved Agentic Evaluator")
    print("=" * 70)
    print("Testing new features:")
    print("  ✓ Multimodal vision (PIL.Image screenshots)")
    print("  ✓ Before/after verification signals")
    print("  ✓ Dialog detection")
    print("  ✓ Stable selector discovery")
    print("  ✓ Extended toolset (wait_for, hover, press_key, etc.)")
    print("=" * 70)
    
    # Create test HTML page with various interactive elements
    test_html = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page - Improved Evaluator</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 { color: #2563eb; margin-bottom: 20px; }
        .button-group { margin: 20px 0; display: flex; gap: 10px; }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            background: #2563eb;
            color: white;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        button:hover { background: #1d4ed8; }
        input {
            padding: 10px;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            width: 100%;
            box-sizing: border-box;
            margin: 10px 0;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            background: #f0fdf4;
            border: 2px solid #86efac;
            border-radius: 6px;
            display: none;
        }
        .result.show { display: block; }
        .counter { font-size: 24px; font-weight: bold; color: #2563eb; }
        .tooltip {
            position: relative;
            display: inline-block;
        }
        .tooltip .tooltiptext {
            visibility: hidden;
            background: #1f2937;
            color: white;
            text-align: center;
            padding: 8px 12px;
            border-radius: 6px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            white-space: nowrap;
        }
        .tooltip:hover .tooltiptext { visibility: visible; }
    </style>
</head>
<body>
    <div class="container">
        <h1 id="title">Interactive Test Page</h1>
        
        <p>This page tests the improved agentic evaluator features.</p>
        
        <div class="button-group">
            <button id="click-test" onclick="handleClick()">Click Me</button>
            <button id="counter-btn" onclick="incrementCounter()">Count: <span class="counter" id="count">0</span></button>
            <div class="tooltip">
                <button id="hover-test">Hover Test</button>
                <span class="tooltiptext">This is a tooltip!</span>
            </div>
        </div>
        
        <div>
            <input id="name-input" type="text" placeholder="Enter your name" />
            <button id="submit-btn" onclick="submitName()">Submit</button>
        </div>
        
        <div id="result" class="result">
            <h3>Result:</h3>
            <p id="result-text"></p>
        </div>
        
        <div style="margin-top: 30px;">
            <button id="dialog-test" onclick="testDialog()">Test Dialog</button>
            <button id="console-error-btn" onclick="triggerError()">Trigger Error</button>
        </div>
    </div>
    
    <script>
        let clickCount = 0;
        let counterValue = 0;
        
        function handleClick() {
            clickCount++;
            const resultDiv = document.getElementById('result');
            const resultText = document.getElementById('result-text');
            resultText.textContent = `Button clicked ${clickCount} time(s)!`;
            resultDiv.classList.add('show');
        }
        
        function incrementCounter() {
            counterValue++;
            document.getElementById('count').textContent = counterValue;
        }
        
        function submitName() {
            const name = document.getElementById('name-input').value;
            if (name) {
                const resultDiv = document.getElementById('result');
                const resultText = document.getElementById('result-text');
                resultText.textContent = `Hello, ${name}! Welcome to the test page.`;
                resultDiv.classList.add('show');
            }
        }
        
        function testDialog() {
            // This should be detected by our dialog wrapper
            alert('This is a test dialog - should be detected!');
        }
        
        function triggerError() {
            // Intentional console error for testing
            console.error('Test error: This is intentional for testing console error detection');
            const resultDiv = document.getElementById('result');
            const resultText = document.getElementById('result-text');
            resultText.textContent = 'Console error triggered (check console)';
            resultDiv.classList.add('show');
        }
        
        // Log page load
        console.log('Test page loaded successfully');
    </script>
</body>
</html>"""
    
    # Create test directory and HTML file
    test_dir = Path("/tmp/agentic_test")
    test_dir.mkdir(exist_ok=True)
    
    html_path = test_dir / "test_page.html"
    html_path.write_text(test_html)
    
    screenshots_dir = test_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Initialize evaluator and MCP client
    evaluator = AgenticEvaluator(max_exploration_steps=12)
    mcp_client = PlaywrightMCPClient()
    
    try:
        # Connect MCP
        print("\n🌐 Starting Playwright MCP server...")
        await mcp_client.connect()
        print("✅ MCP connected")
        
        # Test URL
        url = f"file://{html_path.absolute()}"
        print(f"\n📄 Testing URL: {url}")
        
        task = """Build an interactive test page with:
1. A clickable button that shows feedback
2. A counter button that increments
3. An input field with submit button
4. Buttons to test dialog detection and console errors
All interactions should work and provide visual feedback."""
        
        print(f"\n📋 Task: {task}\n")
        
        # Run evaluation
        print("🤖 Running improved agentic evaluation...")
        print("=" * 70)
        
        result = await evaluator.evaluate_page(
            url=url,
            mcp_client=mcp_client,
            task=task,
            artifacts_dir=screenshots_dir
        )
        
        # Display results
        print("\n" + "=" * 70)
        print("📊 EVALUATION RESULTS")
        print("=" * 70)
        print(f"Score: {result.score}/100")
        print(f"Passed: {'✅ YES' if result.passed else '❌ NO'}")
        
        print(f"\n📈 Category Scores:")
        for category, score in result.category_scores.items():
            max_score = {"functionality": 25, "visual_design": 25, "ux": 15, 
                        "accessibility": 15, "responsiveness": 15, "robustness": 5}.get(category, 0)
            print(f"  {category:20s}: {score:2d}/{max_score}")
        
        print(f"\n🔍 Issues Found: {len(result.issues)}")
        for i, issue in enumerate(result.issues[:5], 1):
            print(f"  {i}. [{issue.severity}] {issue.description[:80]}")
        
        # Check exploration log
        log_file = screenshots_dir / "agentic_exploration.json"
        if log_file.exists():
            with open(log_file) as f:
                log = json.load(f)
            
            print(f"\n📝 Exploration Log:")
            print(f"  Total steps: {log['total_steps']}")
            print(f"  Completion: {log['completion_reason']}")
            
            print(f"\n🔧 Actions Taken:")
            for step in log['exploration_steps'][:10]:  # Show first 10
                tool = step['tool']
                args = step.get('args', {})
                reasoning = step.get('reasoning', '')[:80]
                
                print(f"\n  Step {step['step']}: {tool}")
                if args:
                    print(f"    Args: {args}")
                if reasoning:
                    print(f"    💭 {reasoning}")
                
                # Show verification if available
                if 'verification' in step:
                    v = step['verification']
                    changes = []
                    if v.get('dom_changed'):
                        changes.append('DOM✓')
                    if v.get('text_changed'):
                        changes.append('Text✓')
                    if v.get('new_console_errors'):
                        changes.append(f"Errors+{len(v['new_console_errors'])}")
                    if v.get('dialogs'):
                        changes.append(f"Dialogs+{len(v['dialogs'])}")
                    if changes:
                        print(f"    🔍 Verified: {', '.join(changes)}")
        
        # Check artifacts
        print(f"\n📁 Artifacts Generated:")
        screenshot_count = len(list(screenshots_dir.glob("*.png")))
        json_count = len(list(screenshots_dir.glob("*.json")))
        print(f"  Screenshots: {screenshot_count}")
        print(f"  JSON files: {json_count}")
        print(f"  Location: {screenshots_dir}")
        
        # Verify improvements worked
        print(f"\n✨ Improvement Verification:")
        
        # Check multimodal (screenshots in log)
        has_screenshots = any('screenshot' in step.get('before_state', {}) 
                            for step in log.get('exploration_steps', []))
        print(f"  {'✅' if has_screenshots else '❌'} Multimodal: Screenshots captured")
        
        # Check verification signals
        has_verification = any('verification' in step 
                              for step in log.get('exploration_steps', []))
        print(f"  {'✅' if has_verification else '❌'} Verification: Before/after signals")
        
        # Check dialog detection (should be in verification)
        dialogs_detected = any(len(step.get('verification', {}).get('dialogs', [])) > 0 
                              for step in log.get('exploration_steps', []))
        print(f"  {'✅' if dialogs_detected else '⚠️ '} Dialog detection: {'Dialogs found' if dialogs_detected else 'No dialogs triggered'}")
        
        # Check tools used
        tools_used = set(step['tool'] for step in log.get('exploration_steps', []))
        new_tools = tools_used & {'browser_wait_for', 'browser_hover', 'browser_press_key', 
                                  'browser_get_url', 'browser_dom_snapshot'}
        print(f"  {'✅' if new_tools else '⚠️ '} Extended tools: {len(new_tools)} new tools used")
        if new_tools:
            print(f"      Used: {', '.join(new_tools)}")
        
        # Check stable selectors (IDs used)
        id_selectors = any('#' in str(step.get('args', {}).get('selector', ''))
                          for step in log.get('exploration_steps', []))
        print(f"  {'✅' if id_selectors else '⚠️ '} Stable selectors: {'ID-based selectors used' if id_selectors else 'No ID selectors'}")
        
        print("\n" + "=" * 70)
        print("✅ Test complete! Check artifacts for detailed logs.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔌 Disconnecting MCP...")
        await mcp_client.disconnect()
        print("✅ Cleanup complete")

if __name__ == "__main__":
    asyncio.run(test_improved_evaluator())
