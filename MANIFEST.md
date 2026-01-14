# Run Manifest

Every GeminiLoop run creates a `manifest.json` file that records comprehensive metadata for reproducibility and tracking.

## Location

```
/runs/<run_id>/artifacts/manifest.json
```

## Purpose

The manifest provides a complete snapshot of:
- **Run configuration** - What was requested
- **System versions** - Which models were used
- **Execution details** - How long it took, how many iterations
- **Results** - Final score and pass/fail status  
- **GitHub integration** - Commits made during the run (if enabled)
- **Stop reason** - Why the run ended

Perfect for:
- 🔍 **Debugging** - Understand what happened in a run
- 📊 **Analytics** - Track model performance over time
- 🔄 **Reproducibility** - Re-run with same configuration
- 📈 **Reporting** - Generate summaries and charts

## Schema

### Run Identification

```json
{
  "run_id": "20260113_123456_abc123de",
  "task": "Create a quiz app with 5 questions"
}
```

### Timestamps

```json
{
  "start_time": "2026-01-13T12:34:56.789012",
  "end_time": "2026-01-13T12:35:23.456789",
  "duration_seconds": 26.667777
}
```

### Model Versions

```json
{
  "gemini_model_version": "gemini-2.0-flash-exp",
  "evaluator_model_version": "gemini-2.0-flash-exp",
  "rubric_version": "1.0",
  "openhands_mode": "mock"
}
```

### Run Configuration

```json
{
  "max_iterations": 2,
  "iteration_count": 2
}
```

### Results

```json
{
  "final_score": 85,
  "final_passed": true,
  "stop_reason": "passed"
}
```

**Stop Reasons:**
- `passed` - Evaluation passed (score ≥ 70)
- `max_iterations` - Reached iteration limit
- `completed` - Finished normally
- `failed` - Evaluation failed
- `error` - Execution error occurred

### GitHub Integration (Optional)

```json
{
  "github_enabled": true,
  "github_repo": "username/template-repo",
  "github_branch": "run/20260113_123456_abc123de",
  "github_base_branch": "main",
  "github_commits": [
    {
      "iteration": 1,
      "commit_sha": "abc123def456789...",
      "commit_url": "https://github.com/username/template-repo/commit/abc123...",
      "timestamp": "2026-01-13T12:35:15.123456"
    },
    {
      "iteration": 2,
      "commit_sha": "def456ghi789abc...",
      "commit_url": "https://github.com/username/template-repo/commit/def456...",
      "timestamp": "2026-01-13T12:35:20.654321"
    }
  ]
}
```

### Artifact Paths

```json
{
  "workspace_dir": "/app/runs/20260113_123456_abc123de/workspace",
  "artifacts_dir": "/app/runs/20260113_123456_abc123de/artifacts",
  "site_dir": "/app/runs/20260113_123456_abc123de/site",
  "preview_url": "http://localhost:8080/preview/20260113_123456_abc123de/"
}
```

### Error Information (If Failed)

```json
{
  "error_message": "Timeout waiting for page to load",
  "stop_reason": "error"
}
```

## Complete Example

```json
{
  "run_id": "20260113_123456_abc123de",
  "task": "Create a quiz app with 5 questions",
  "start_time": "2026-01-13T12:34:56.789012",
  "end_time": "2026-01-13T12:35:23.456789",
  "duration_seconds": 26.667777,
  "gemini_model_version": "gemini-2.0-flash-exp",
  "evaluator_model_version": "gemini-2.0-flash-exp",
  "rubric_version": "1.0",
  "openhands_mode": "mock",
  "max_iterations": 2,
  "iteration_count": 2,
  "final_score": 85,
  "final_passed": true,
  "stop_reason": "passed",
  "github_enabled": true,
  "github_repo": "username/template-repo",
  "github_branch": "run/20260113_123456_abc123de",
  "github_base_branch": "main",
  "github_commits": [
    {
      "iteration": 1,
      "commit_sha": "abc123def456",
      "commit_url": "https://github.com/username/template-repo/commit/abc123def456",
      "timestamp": "2026-01-13T12:35:15.123456"
    },
    {
      "iteration": 2,
      "commit_sha": "def456ghi789",
      "commit_url": "https://github.com/username/template-repo/commit/def456ghi789",
      "timestamp": "2026-01-13T12:35:20.654321"
    }
  ],
  "workspace_dir": "/app/runs/20260113_123456_abc123de/workspace",
  "artifacts_dir": "/app/runs/20260113_123456_abc123de/artifacts",
  "site_dir": "/app/runs/20260113_123456_abc123de/site",
  "preview_url": "http://localhost:8080/preview/20260113_123456_abc123de/",
  "error_message": null
}
```

## Usage

### Read Manifest

```bash
# View manifest
cat runs/*/artifacts/manifest.json | jq '.'

# Get specific fields
cat runs/*/artifacts/manifest.json | jq '.final_score'
cat runs/*/artifacts/manifest.json | jq '.github_commits'
cat runs/*/artifacts/manifest.json | jq '.duration_seconds'
```

### Filter Runs

```bash
# Find passed runs
for manifest in runs/*/artifacts/manifest.json; do
  jq -r 'select(.final_passed == true) | .run_id' "$manifest"
done

# Find runs with GitHub commits
for manifest in runs/*/artifacts/manifest.json; do
  jq -r 'select(.github_enabled == true) | .run_id' "$manifest"
done

# Find failed runs
for manifest in runs/*/artifacts/manifest.json; do
  jq -r 'select(.stop_reason == "error") | "\(.run_id): \(.error_message)"' "$manifest"
done
```

### Analytics

```bash
# Average score across all runs
jq -s '[.[] | .final_score] | add / length' runs/*/artifacts/manifest.json

# Average duration
jq -s '[.[] | .duration_seconds] | add / length' runs/*/artifacts/manifest.json

# Success rate
jq -s '([.[] | select(.final_passed == true)] | length) / length * 100' runs/*/artifacts/manifest.json

# Count by stop reason
jq -s 'group_by(.stop_reason) | map({reason: .[0].stop_reason, count: length})' runs/*/artifacts/manifest.json
```

### Compare Runs

```bash
# Compare two runs
diff <(jq '.' runs/run1/artifacts/manifest.json) <(jq '.' runs/run2/artifacts/manifest.json)

# Compare scores
jq -s 'map({run_id, final_score}) | sort_by(.final_score) | reverse' runs/*/artifacts/manifest.json
```

## Integration

### In Python

```python
import json
from pathlib import Path

# Load manifest
manifest_file = Path("runs/my-run-123/artifacts/manifest.json")
with open(manifest_file) as f:
    manifest = json.load(f)

# Access data
print(f"Run ID: {manifest['run_id']}")
print(f"Score: {manifest['final_score']}")
print(f"Duration: {manifest['duration_seconds']:.2f}s")
print(f"GitHub commits: {len(manifest['github_commits'])}")

# Check if passed
if manifest['final_passed']:
    print("✅ Run passed!")
else:
    print(f"❌ Run failed: {manifest['stop_reason']}")
```

### In Shell Scripts

```bash
#!/bin/bash

# Get latest run ID
LATEST_RUN=$(ls -t runs/*/artifacts/manifest.json | head -1 | cut -d'/' -f2)

# Load manifest
MANIFEST="runs/$LATEST_RUN/artifacts/manifest.json"

# Extract fields
SCORE=$(jq -r '.final_score' "$MANIFEST")
PASSED=$(jq -r '.final_passed' "$MANIFEST")
DURATION=$(jq -r '.duration_seconds' "$MANIFEST")

# Report
echo "Latest run: $LATEST_RUN"
echo "Score: $SCORE/100"
echo "Passed: $PASSED"
echo "Duration: ${DURATION}s"
```

## Fields Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | string | ✅ | Unique run identifier |
| `task` | string | ✅ | Task description |
| `start_time` | ISO8601 | ✅ | Run start timestamp |
| `end_time` | ISO8601 | ✅ | Run end timestamp |
| `duration_seconds` | number | ✅ | Total duration |
| `gemini_model_version` | string | ✅ | Gemini model used |
| `evaluator_model_version` | string | ✅ | Evaluator model used |
| `rubric_version` | string | ✅ | Rubric version |
| `openhands_mode` | string | ✅ | OpenHands mode (mock/local) |
| `max_iterations` | number | ✅ | Maximum iterations allowed |
| `iteration_count` | number | ✅ | Iterations completed |
| `final_score` | number | ✅ | Final evaluation score (0-100) |
| `final_passed` | boolean | ✅ | Whether evaluation passed |
| `stop_reason` | string | ✅ | Why the run stopped |
| `github_enabled` | boolean | ✅ | GitHub integration enabled |
| `github_repo` | string | ❌ | GitHub repository |
| `github_branch` | string | ❌ | Run branch name |
| `github_base_branch` | string | ❌ | Base branch |
| `github_commits` | array | ❌ | Commits made during run |
| `workspace_dir` | string | ✅ | Workspace directory path |
| `artifacts_dir` | string | ✅ | Artifacts directory path |
| `site_dir` | string | ✅ | Site directory path |
| `preview_url` | string | ✅ | Preview URL |
| `error_message` | string | ❌ | Error message (if failed) |

## Benefits

### 1. Reproducibility

Know exactly what configuration and models were used:

```bash
# Re-run with same config
jq -r '.gemini_model_version, .max_iterations, .openhands_mode' manifest.json
```

### 2. Debugging

Trace issues with complete context:

```bash
# Failed runs
jq 'select(.stop_reason == "error") | {run_id, error_message, duration_seconds}' manifest.json
```

### 3. Analytics

Track performance over time:

```bash
# Score trends
jq -s 'map({run_id, score: .final_score, time: .start_time}) | sort_by(.time)' runs/*/artifacts/manifest.json
```

### 4. Auditing

Complete audit trail with timestamps and versions:

```bash
# Audit report
jq '{run_id, task, start_time, final_score, github_commits: (.github_commits | length)}' manifest.json
```

## Versioning

The manifest schema follows semantic versioning:

- **Current version**: Implicit 1.0 (tracked via `rubric_version`)
- **Breaking changes**: Will increment major version
- **New fields**: Will increment minor version (backward compatible)
- **Fixes**: Will increment patch version

## Best Practices

### 1. Always Check Manifest

Before analyzing a run:

```bash
# Verify manifest exists
if [ -f "runs/$RUN_ID/artifacts/manifest.json" ]; then
  echo "Manifest found"
else
  echo "ERROR: Manifest missing"
  exit 1
fi
```

### 2. Use jq for Parsing

Never parse JSON manually:

```bash
# Good
SCORE=$(jq -r '.final_score' manifest.json)

# Bad
SCORE=$(grep final_score manifest.json | cut -d':' -f2)
```

### 3. Archive Manifests

Keep manifests for long-term analysis:

```bash
# Archive monthly
tar -czf manifests-2026-01.tar.gz runs/*/artifacts/manifest.json
```

### 4. Validate Schema

Ensure manifests are well-formed:

```bash
# Validate JSON
jq empty manifest.json && echo "Valid" || echo "Invalid"

# Check required fields
jq 'has("run_id", "task", "start_time")' manifest.json
```

## Summary

✅ **Comprehensive** - All run metadata in one file  
✅ **Machine-readable** - JSON format for easy parsing  
✅ **Searchable** - Use jq for powerful queries  
✅ **Versionable** - Track model and rubric versions  
✅ **Auditable** - Complete timeline with GitHub commits  
✅ **Reproducible** - Know exactly how to re-run  

**Every run writes a manifest automatically - no configuration needed!**

---

## Quick Reference

```bash
# View manifest
cat runs/<run_id>/artifacts/manifest.json | jq '.'

# Get score
jq '.final_score' manifest.json

# Get GitHub commits
jq '.github_commits' manifest.json

# Check if passed
jq '.final_passed' manifest.json

# Get duration
jq '.duration_seconds' manifest.json

# Get stop reason
jq '.stop_reason' manifest.json
```

---

**See also:** [run_state.py](orchestrator/run_state.py) - RunManifest implementation
