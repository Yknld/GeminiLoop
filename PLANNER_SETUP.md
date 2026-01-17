# Planner Setup Guide

This guide explains the new prompt-based architecture using Gemini 3.0 Pro Preview as a planner.

## Architecture Overview

```
User Requirements
        ↓
Gemini 3.0 Pro Preview (Planner)
    - Analyzes requirements
    - Thinks through implementation
    - Generates detailed prompt (5000+ chars)
        ↓
OpenHands
    - Creates single HTML file from scratch
    - Implements all features based on prompt
        ↓
Playwright Testing
        ↓
Gemini Vision Evaluation
        ↓
Iterate if needed
```

## Setup Steps

### 1. Paste Your Planner Prompt

Open this file:
```
orchestrator/prompts/planner_prompt.txt
```

Replace the placeholder with your complete planner prompt. This prompt should instruct Gemini how to:
- Analyze user requirements
- Think through technical implementation
- Generate a comprehensive prompt for OpenHands
- Ensure single HTML file output with inline CSS/JS

### 2. Test the Planner

Once you've pasted your prompt, test it:

```bash
# Test with default task
./test_planner.sh

# Test with custom task
./test_planner.sh "Create a todo app with add/delete/complete functionality"
```

This will:
- Load your planner prompt
- Call Gemini 3.0 Pro Preview
- Generate a detailed OpenHands prompt
- Display the result

Expected output:
```
================================================================================
GENERATED OPENHANDS PROMPT:
================================================================================
[Long detailed prompt with technical specs, requirements, constraints, etc.]
================================================================================

THINKING PROCESS:
================================================================================
[Gemini's thinking about how to approach the task]
================================================================================
```

### 3. Run Full Orchestrator

Once the planner works, run the full system:

```bash
python3 -m orchestrator.main "Create a quiz app about geography"
```

The flow will be:
1. **Planning Phase**: Gemini 3.0 Pro Preview generates detailed prompt
2. **Generation Phase**: OpenHands creates HTML from scratch using the prompt
3. **Testing Phase**: Playwright tests the generated HTML
4. **Evaluation Phase**: Gemini Vision evaluates quality
5. **Iteration**: Fix issues and repeat if needed

### 4. Review Artifacts

After running, check:
```
runs/<run_id>/artifacts/
    planner_output.json      # Full plan with metadata
    openhands_prompt.txt     # The prompt sent to OpenHands
    planner_thinking.txt     # Gemini's thinking process
    screenshot_*.png         # Test screenshots
    evaluation_*.json        # Quality evaluations
```

## File Structure

```
orchestrator/
├── planner.py                      # Planner module (Gemini 3.0 Pro Preview)
├── prompts/
│   ├── planner_prompt.txt         # YOUR PROMPT GOES HERE
│   └── README.md                  # Prompt guidelines
└── main.py                        # Updated with planner integration
```

## Key Changes from Template System

### Before (Template-Based)
```python
# Load template HTML
template = load_template("template.html")

# Generate with Gemini
code = gemini.generate_code(task)

# Populate template
result = template.render(code)
```

### After (Prompt-Based)
```python
# Generate detailed prompt with Gemini 3.0 Pro Preview
plan = planner.generate_openhands_prompt(user_requirements)

# OpenHands creates HTML from scratch
result = openhands.generate_code(plan['prompt'])
```

## Benefits

1. **No Template Constraints**: OpenHands starts from scratch every time
2. **Better Thinking**: Gemini 3.0 Pro Preview provides deep analysis
3. **Flexible Output**: Can create any structure, not limited by template
4. **Detailed Instructions**: 5000+ character prompts with full specs
5. **Transparency**: See Gemini's thinking process

## Docker Integration

The planner works seamlessly in Docker:

```bash
# Build Docker image
docker build -t gemini-loop .

# Run with environment variables
docker run -p 8080:8080 \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  -v $(pwd)/runs:/app/runs \
  gemini-loop
```

The Dockerfile already includes:
- Python 3.12 with all dependencies
- Node.js 22 for OpenHands
- Playwright + Chromium for testing
- All orchestrator files including planner

## Testing in Docker

### Local Test
```bash
docker run -it --rm \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  gemini-loop \
  python3 -m orchestrator.planner "Create a calculator app"
```

### Full Run
```bash
docker run -it --rm \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  -v $(pwd)/runs:/app/runs \
  gemini-loop \
  python3 -m orchestrator.main "Create a calculator app"
```

## Environment Variables

Required:
- `GOOGLE_AI_STUDIO_API_KEY` - Your Google AI Studio API key

Optional:
- `AGENTIC_EVAL` - Use agentic evaluator (default: true)
- `OPENHANDS_MODE` - OpenHands mode: local, mock (default: mock)
- `HEADLESS` - Run browser headless (default: true)

## Troubleshooting

### "Planner prompt not found"
- Make sure you pasted your prompt into `orchestrator/prompts/planner_prompt.txt`
- Check the file exists and isn't empty

### "GOOGLE_AI_STUDIO_API_KEY not set"
- Set the environment variable: `export GOOGLE_AI_STUDIO_API_KEY=your_key`
- Or pass it to Docker: `-e GOOGLE_AI_STUDIO_API_KEY=your_key`

### "Gemini 3.0 Pro Preview not available"
- Make sure you're using the latest google-generativeai package
- Check your API key has access to Gemini 2.0 models
- Model name: `gemini-3-pro-preview`

### "OpenHands generation failed"
- Check the generated prompt in `artifacts/openhands_prompt.txt`
- Ensure your planner prompt produces clear, actionable instructions
- Verify OpenHands has write access to workspace directory

### "Generated HTML is incomplete"
- Review `artifacts/planner_thinking.txt` for Gemini's reasoning
- Adjust your planner prompt to be more specific
- Add more constraints and examples in the prompt

## Prompt Writing Tips

Your planner prompt should:

1. **Set Context**: Explain what Gemini is doing
2. **Define Output**: Single HTML file, inline CSS/JS, no dependencies
3. **Specify Quality**: Accessibility, mobile-friendly, error-free
4. **Include Examples**: Show what good prompts look like
5. **Request Thinking**: Ask Gemini to think through the problem
6. **Be Comprehensive**: Cover all technical requirements

Example structure:
```
You are a senior technical architect generating detailed implementation
prompts for an AI coding assistant (OpenHands).

[Context about the system]
[Technical constraints]
[Quality requirements]
[Output format instructions]
[Examples of good prompts]

Now analyze the user requirements and generate a detailed prompt...
```

## Next Steps

1. ✅ Paste your planner prompt
2. ✅ Test with `./test_planner.sh`
3. ✅ Review generated output
4. ✅ Adjust prompt if needed
5. ✅ Run full orchestrator
6. ✅ Check artifacts directory
7. ✅ Iterate on prompt based on results

## Questions?

- Check `orchestrator/prompts/README.md` for prompt guidelines
- Review generated artifacts in `runs/<run_id>/artifacts/`
- Test planner standalone: `python3 -m orchestrator.planner "Your task"`
- See full docs: `COURSE_STRUCTURE.md`, `TESTING_GUIDE.md`

---

**Ready to Go!** Just paste your prompt and start testing.
