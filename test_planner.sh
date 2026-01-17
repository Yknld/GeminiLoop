#!/bin/bash
# Test the planner with a sample task

set -e

echo "🧪 Testing Planner Module"
echo "========================="
echo ""

# Check if planner prompt exists
if [ ! -f "orchestrator/prompts/planner_prompt.txt" ]; then
    echo "❌ Error: planner_prompt.txt not found!"
    echo "   Please paste your prompt into:"
    echo "   orchestrator/prompts/planner_prompt.txt"
    exit 1
fi

# Check if it's still the placeholder
if grep -q "\[PASTE YOUR PLANNER PROMPT HERE\]" orchestrator/prompts/planner_prompt.txt; then
    echo "❌ Error: Planner prompt is still a placeholder!"
    echo "   Please paste your actual prompt into:"
    echo "   orchestrator/prompts/planner_prompt.txt"
    exit 1
fi

# Get task from args or use default
TASK="${1:-Create a simple quiz app about geography with multiple choice questions}"

echo "📋 Task: $TASK"
echo ""
echo "🧠 Running planner (Gemini 3.0 Pro Preview)..."
echo ""

# Run the planner
python3 -m orchestrator.planner "$TASK"

echo ""
echo "✅ Test complete!"
echo ""
echo "Generated files should be displayed above."
echo "When running the full orchestrator, they will be saved to:"
echo "  runs/<run_id>/artifacts/planner_output.json"
echo "  runs/<run_id>/artifacts/openhands_prompt.txt"
echo "  runs/<run_id>/artifacts/planner_thinking.txt"
