# Using Custom Notes/Prompts via API

You can now send custom notes/prompts directly to OpenHands, bypassing the planner.

## API Usage

### Basic Request (with Planner)

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create an interactive lesson about probability"
    }
  }'
```

### Request with Custom Notes (Skip Planner)

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create an interactive lesson",
      "notes": "Create a single HTML file with tabbed navigation. Include:\n\n1. Intro section with welcome message\n2. Coins section with interactive coin flip simulation\n3. Dice section with rolling dice and statistics\n4. Law of Large Numbers section with visualization\n5. Summary section with expected value game\n\nAll interactions must use DOM-visible feedback (toasts, not alerts). Use modern, clean design with good spacing and colors."
    }
  }'
```

## How It Works

1. **If `notes` is provided**: The custom notes are used directly as the prompt for OpenHands (planner is skipped)
2. **If `notes` is NOT provided**: The planner generates a detailed prompt from the `task` (default behavior)

## Benefits

- **Full Control**: Write your own detailed instructions for OpenHands
- **Faster**: Skip the planner step (saves ~10-20 seconds)
- **Consistent**: Use the same prompt across multiple runs
- **Flexible**: Mix and match - use planner for some tasks, custom notes for others

## Example: Reusing the Same Prompt

```bash
# Save your notes to a file
cat > my_notes.txt << 'EOF'
Create a single HTML file with tabbed navigation for teaching probability.
Include coin flips, dice rolling, and law of large numbers visualization.
All in one self-contained file with inline CSS and JavaScript.
EOF

# Use it in API calls
NOTES=$(cat my_notes.txt)
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": {
      \"task\": \"Probability lesson\",
      \"notes\": $(python3 -c "import json, sys; print(json.dumps(sys.stdin.read()))" <<< "$NOTES")
    }
  }"
```

## Notes Format

Your custom notes should:
- Be clear and specific
- Include technical requirements (single HTML file, inline CSS/JS, no external dependencies)
- Specify what sections/content to include
- Mention interaction requirements (DOM-visible feedback, no alerts)
- Include design preferences if desired

The notes are saved to `artifacts/custom_notes.txt` for reference.
