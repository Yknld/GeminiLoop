# Planner Prompts

This directory contains prompt templates for the planning phase.

## Files

### planner_prompt.txt

The main prompt used by Gemini 3.0 Pro Preview to generate detailed, descriptive prompts for OpenHands.

**Purpose**: This prompt instructs Gemini how to:
1. Analyze user requirements
2. Think through implementation details
3. Generate a comprehensive prompt for OpenHands
4. Ensure the output is a single, self-contained HTML file

**Usage**: The planner loads this file and combines it with user requirements to generate the final OpenHands prompt.

**How to Edit**:
1. Open `planner_prompt.txt`
2. Modify the instructions as needed
3. Test with: `python -m orchestrator.planner "Create a quiz app"`
4. Review the generated output

## Prompt Structure

A good planner prompt should:
- Be clear and specific
- Include technical requirements (single HTML file, inline CSS/JS, no dependencies)
- Specify quality criteria (accessibility, mobile-friendly, no console errors)
- Guide Gemini's thinking process
- Result in a detailed prompt that OpenHands can execute

## Example Flow

```
User Input: "Create a quiz app about geography"
        ↓
Planner (Gemini 3.0 Pro Preview)
    - Reads planner_prompt.txt
    - Analyzes user requirements
    - Thinks through implementation
    - Generates detailed prompt
        ↓
Generated Prompt (5000+ chars with detailed specs)
        ↓
OpenHands
    - Creates single HTML file from scratch
    - Implements all features
    - Returns completed code
```

## Tips for Writing Good Planner Prompts

1. **Be Explicit**: Don't assume anything. Spell out exactly what you want.
2. **Include Examples**: Show Gemini what good output looks like.
3. **Set Constraints**: "Single HTML file", "No external dependencies", etc.
4. **Request Thinking**: Ask Gemini to think through the problem first.
5. **Specify Format**: Define how the output should be structured.
6. **Quality Standards**: Include accessibility, responsiveness, error handling.

## Testing

Test your planner prompt:

```bash
# Quick test
python -m orchestrator.planner "Create a todo app"

# Full integration test
python -m orchestrator.main "Create a todo app"
```

Review the generated files in `runs/<run_id>/artifacts/`:
- `planner_output.json` - Full plan with metadata
- `openhands_prompt.txt` - The prompt sent to OpenHands
- `planner_thinking.txt` - Gemini's thinking process (if available)
