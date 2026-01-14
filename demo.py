#!/usr/bin/env python3
"""
GeminiLoop Demo Script

Demonstrates the system with various example tasks
"""

import asyncio
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.main import run_loop


DEMO_TASKS = [
    {
        "name": "Simple Landing Page",
        "task": "Create a modern landing page for a SaaS product with hero section, features grid, and call-to-action button"
    },
    {
        "name": "Todo App",
        "task": "Create a todo list app with add, delete, and mark complete functionality using local storage"
    },
    {
        "name": "Contact Form",
        "task": "Create a contact form with name, email, message fields and submit button with validation"
    },
    {
        "name": "Pricing Cards",
        "task": "Create a pricing section with 3 cards (Basic, Pro, Enterprise) with features and pricing"
    },
    {
        "name": "Dashboard",
        "task": "Create a simple dashboard with sidebar navigation, stats cards, and a chart placeholder"
    }
]


async def run_demo(task_index: int = 0):
    """Run a demo task"""
    
    if task_index >= len(DEMO_TASKS):
        print(f"❌ Invalid task index. Choose 0-{len(DEMO_TASKS) - 1}")
        return
    
    demo = DEMO_TASKS[task_index]
    
    print("=" * 70)
    print(f"🎬 GeminiLoop Demo: {demo['name']}")
    print("=" * 70)
    print()
    
    # Run the loop
    state = await run_loop(demo["task"], max_iterations=3)
    
    print()
    print("=" * 70)
    print("✅ Demo Complete!")
    print("=" * 70)
    print(f"Run ID: {state.run_id}")
    print(f"Score: {state.score}/100")
    print(f"Status: {'PASSED ✅' if state.passed else 'FAILED ❌'}")
    print(f"Preview: {state.get_preview_url()}")
    print()


def list_demos():
    """List available demos"""
    print("Available demos:")
    print()
    for i, demo in enumerate(DEMO_TASKS):
        print(f"{i}. {demo['name']}")
        print(f"   Task: {demo['task']}")
        print()


async def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_demos()
            return
        
        try:
            task_index = int(sys.argv[1])
            await run_demo(task_index)
        except ValueError:
            print("Usage: python demo.py [task_index|list]")
            print()
            list_demos()
    else:
        print("Usage: python demo.py [task_index|list]")
        print()
        list_demos()
        print("Example: python demo.py 0")


if __name__ == "__main__":
    asyncio.run(main())
