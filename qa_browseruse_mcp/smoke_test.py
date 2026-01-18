"""
Smoke test for BrowserUse MCP

Tests basic functionality: navigate → screenshot → dom_snapshot → 
interactive_elements → click first link → screenshot again
"""

import asyncio
import sys
import argparse
from pathlib import Path

from .client import BrowserUseMCPClient


async def run_smoke(url: str, base_url: str = None):
    """Run smoke test"""
    print(f"🚀 Starting smoke test for: {url}")
    if base_url:
        print(f"   MCP Server: {base_url}")
    else:
        print(f"   Mode: In-process (no server needed)")
    
    client = BrowserUseMCPClient(base_url=base_url, headless=True)
    
    try:
        # Navigate
        print("\n1️⃣  Navigating...")
        success = await client.navigate(url)
        if not success:
            print("   ❌ Navigation failed")
            return False
        print("   ✅ Navigation successful")
        
        # Screenshot
        print("\n2️⃣  Taking screenshot (before)...")
        screenshot_path = Path("before.png")
        try:
            await client.screenshot(screenshot_path)
            print(f"   ✅ Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"   ❌ Screenshot failed: {e}")
            return False
        
        # DOM snapshot
        print("\n3️⃣  Getting DOM snapshot...")
        try:
            snapshot = await client.snapshot()
            print(f"   ✅ Snapshot successful")
            print(f"      Title: {snapshot.get('title', 'N/A')}")
            print(f"      Buttons: {len(snapshot.get('buttons', []))}")
            interactive_elements = snapshot.get("interactive_elements", [])
            print(f"      Interactive elements: {len(interactive_elements)}")
        except Exception as e:
            print(f"   ❌ Snapshot failed: {e}")
            return False
        
        # Interactive elements
        print("\n4️⃣  Getting interactive elements...")
        try:
            elements = await client.interactive_elements(max_interactive=50)
            print(f"   ✅ Found {len(elements)} interactive elements")
            if elements:
                first = elements[0]
                print(f"      First element: {first.tag} - '{first.text[:50]}' (selector: {first.selector})")
        except Exception as e:
            print(f"   ❌ Interactive elements failed: {e}")
            return False
        
        # Click first link if available
        if elements:
            # Find first clickable element (link or button)
            clickable = None
            for el in elements:
                if el.tag in ["a", "button"] and el.visible and not el.disabled:
                    clickable = el
                    break
            
            if clickable:
                print(f"\n5️⃣  Clicking first clickable element: {clickable.selector}")
                try:
                    success = await client.click(clickable.selector)
                    if success:
                        print(f"   ✅ Click successful")
                        # Wait a bit for page to update
                        await asyncio.sleep(1)
                    else:
                        print(f"   ⚠️  Click returned False (may have worked)")
                except Exception as e:
                    print(f"   ⚠️  Click failed: {e} (continuing anyway)")
            else:
                print("\n5️⃣  No clickable elements found, skipping click")
        else:
            print("\n5️⃣  No interactive elements found, skipping click")
        
        # Screenshot after
        print("\n6️⃣  Taking screenshot (after)...")
        screenshot_path_after = Path("after.png")
        try:
            await client.screenshot(screenshot_path_after)
            print(f"   ✅ Screenshot saved: {screenshot_path_after}")
        except Exception as e:
            print(f"   ⚠️  Screenshot failed: {e} (continuing anyway)")
        
        # Get console
        print("\n7️⃣  Getting console messages...")
        try:
            console = await client.get_console()
            errors = [m for m in console if m.get("level") == "error" or m.get("type") == "error"]
            print(f"   ✅ Console messages: {len(console)} total, {len(errors)} errors")
            if errors:
                print(f"      First error: {errors[0].get('message', 'N/A')[:100]}")
        except Exception as e:
            print(f"   ⚠️  Console failed: {e} (continuing anyway)")
        
        # Test video recording (optional)
        print("\n8️⃣  Testing video recording...")
        try:
            video_path = Path("test_recording.webm")
            success = await client.start_recording(str(video_path))
            if success:
                print(f"   ✅ Video recording started: {video_path}")
                # Wait a bit
                await asyncio.sleep(2)
                # Stop recording
                saved_path = await client.stop_recording()
                if saved_path and Path(saved_path).exists():
                    print(f"   ✅ Video recording saved: {saved_path}")
                else:
                    print(f"   ⚠️  Video recording stopped but file not found")
            else:
                print(f"   ⚠️  Video recording failed to start")
        except Exception as e:
            print(f"   ⚠️  Video recording test failed: {e} (continuing anyway)")
        
        print("\n✅ Smoke test completed successfully!")
        print(f"\n📁 Generated files:")
        print(f"   - before.png")
        print(f"   - after.png")
        if Path("test_recording.webm").exists():
            print(f"   - test_recording.webm")
        return True
    
    except Exception as e:
        print(f"\n❌ Smoke test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await client.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Smoke test for BrowserUse MCP")
    parser.add_argument("--url", required=True, help="URL to test")
    parser.add_argument("--base_url", default=None, help="MCP server base URL (None = in-process mode)")
    
    args = parser.parse_args()
    
    success = asyncio.run(run_smoke(args.url, args.base_url))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
