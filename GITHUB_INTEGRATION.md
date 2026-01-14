# GitHub Integration

Automatically create branches, commit changes, and track iterations in GitHub.

## Overview

GeminiLoop includes optional **GitHub template branching** that allows you to:
- Start each run from a template repository
- Create a unique branch for each run (`run/<run_id>`)
- Automatically commit and push after each successful OpenHands patch
- Track the final branch URL in the run report

Perfect for:
- 🔄 Iterative development workflows
- 📊 Tracking changes across iterations
- 👥 Collaborating on generated code
- 📦 Managing template repositories

## Architecture

```
GitHub Template Repo (main)
  ├─ Clone to workspace
  │
  └─ Create branch: run/<run_id>
       ├─ Iteration 1: Initial generation
       ├─ Commit: "[Iteration 1] Apply OpenHands patch"
       │
       ├─ Iteration 2: After patch
       ├─ Commit: "[Iteration 2] Apply OpenHands patch"
       │
       └─ Final: Branch URL in report.json
```

## Setup

### 1. Create GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Click "Generate new token (classic)"
3. Select scopes:
   - ✅ `repo` (full control of private repositories)
4. Copy the token

### 2. Configure Environment

Add to `.env`:

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=owner/repo-name
BASE_BRANCH=main
```

Or set environment variables:

```bash
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_REPO=username/my-template-repo
export BASE_BRANCH=main
```

### 3. Prepare Template Repository

Your template repo should contain:
- Base HTML/CSS/JS files
- Any shared assets
- Configuration files

Example structure:
```
my-template-repo/
├─ index.html
├─ styles.css
├─ script.js
├─ assets/
│  └─ logo.png
└─ README.md
```

## Usage

### Basic Usage

```bash
# Set GitHub credentials
export GITHUB_TOKEN=ghp_...
export GITHUB_REPO=username/web-template

# Run orchestrator
python -m orchestrator.main "Create a quiz app"
```

### What Happens

**1. Run Start:**
- Creates branch `run/quiz-20260113-123456` from `main`
- Clones branch to workspace
- Copies files to site directory

**2. After Each Patch:**
- Commits changes in workspace
- Pushes to `run/<run_id>` branch
- Logs commit SHA and URL

**3. Run Complete:**
- Final report includes branch URL
- All iterations tracked in git history

### Output Example

```
🐙 GitHub integration enabled
   Repo: username/web-template
   Base branch: main

📝 Creating branch: run/quiz-20260113-123456
✅ Branch created: run/quiz-20260113-123456

📥 Cloning run/quiz-20260113-123456 to workspace...
✅ Cloned to: /app/runs/quiz-20260113-123456/workspace

...

🐙 Committing and pushing to GitHub...
   ✅ Pushed to run/quiz-20260113-123456
   Commit: a1b2c3d
   URL: https://github.com/username/web-template/commit/a1b2c3d

...

🏁 FINAL RESULTS
   Run ID: quiz-20260113-123456
   🐙 GitHub: https://github.com/username/web-template/tree/run/quiz-20260113-123456
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_TOKEN` | Yes* | - | GitHub personal access token |
| `GITHUB_REPO` | Yes* | - | Repository in `owner/repo` format |
| `BASE_BRANCH` | No | `main` | Base branch to create run branches from |

*Required for GitHub integration to be enabled

### Branch Naming

Branches are automatically named:
```
run/<run_id>
```

Example:
```
run/quiz-20260113-123456
run/landing-20260113-130000
```

### Commit Messages

Commits follow this pattern:
```
[Iteration N] Apply OpenHands patch (score: X/100)
```

Example:
```
[Iteration 1] Apply OpenHands patch (score: 45/100)
[Iteration 2] Apply OpenHands patch (score: 78/100)
```

## GitHubClient API

The `GitHubClient` class provides three main methods:

### create_branch()

```python
github = GitHubClient(token=token, repo_name=repo, base_branch="main")

result = github.create_branch(
    new_branch="run/my-run-123",
    base_branch="main"  # optional, uses self.base_branch if not provided
)

# Returns:
# {
#   "success": True,
#   "branch": "run/my-run-123",
#   "sha": "abc123...",
#   "message": "Created branch run/my-run-123 from main",
#   "ref": "refs/heads/run/my-run-123"
# }
```

### clone_branch_to_workspace()

```python
result = github.clone_branch_to_workspace(
    branch="run/my-run-123",
    workspace_path=Path("/app/workspace"),
    depth=1  # shallow clone
)

# Returns:
# {
#   "success": True,
#   "workspace": "/app/workspace",
#   "branch": "run/my-run-123",
#   "message": "Cloned username/repo:run/my-run-123",
#   "stdout": "..."
# }
```

### commit_and_push()

```python
result = github.commit_and_push(
    workspace_path=Path("/app/workspace"),
    message="Update code",
    branch="run/my-run-123",
    add_all=True
)

# Returns:
# {
#   "success": True,
#   "branch": "run/my-run-123",
#   "message": "Committed and pushed to run/my-run-123",
#   "commit_sha": "def456...",
#   "commit_url": "https://github.com/username/repo/commit/def456...",
#   "branch_url": "https://github.com/username/repo/tree/run/my-run-123"
# }
```

## Workflow Integration

### In orchestrator/main.py

```python
from .github_client import get_github_client

async def run_loop(task: str, ...):
    # Initialize GitHub client
    github = get_github_client()
    
    # Check if enabled
    if github.is_enabled():
        # Create branch
        run_branch = f"run/{config.run_id}"
        github.create_branch(new_branch=run_branch)
        
        # Clone to workspace
        github.clone_branch_to_workspace(
            branch=run_branch,
            workspace_path=state.workspace_dir
        )
        
        # Store branch info
        state.result.github_branch = run_branch
        state.result.github_branch_url = github.get_branch_url(run_branch)
    
    # ... generation and evaluation ...
    
    # After patch applied
    if github.is_enabled():
        github.commit_and_push(
            workspace_path=state.workspace_dir,
            message=f"[Iteration {iteration}] Apply OpenHands patch",
            branch=run_branch
        )
```

## Report Output

The final `report.json` includes GitHub info:

```json
{
  "run_id": "quiz-20260113-123456",
  "task": "Create a quiz app",
  "status": "completed",
  "final_score": 78,
  "github_branch": "run/quiz-20260113-123456",
  "github_branch_url": "https://github.com/username/web-template/tree/run/quiz-20260113-123456",
  "iterations": [
    {
      "iteration": 1,
      "score": 45,
      "files_generated": {"index.html": "..."}
    },
    {
      "iteration": 2,
      "score": 78,
      "files_generated": {"index.html": "..."}
    }
  ]
}
```

## Fallback Behavior

If GitHub is **not configured** (no token or repo):
- ✅ Orchestrator runs normally
- ✅ Uses template HTML instead of cloning
- ✅ No commits/pushes attempted
- ℹ️  Logs: "GitHub integration disabled"

If GitHub operations **fail**:
- ✅ Continues with local workflow
- ⚠️  Logs warnings
- ✅ Falls back to template if clone fails

**GitHub integration is optional and non-blocking.**

## Use Cases

### 1. Template-Based Projects

**Scenario:** You have a standard web template you want to iterate on.

```bash
# Template repo: username/web-starter
# Contains: boilerplate HTML, CSS, JS

export GITHUB_REPO=username/web-starter
export GITHUB_TOKEN=ghp_...

python -m orchestrator.main "Add contact form"
```

**Result:** New branch with form added, tracked in git history.

### 2. Multi-User Collaboration

**Scenario:** Multiple developers running GeminiLoop on shared template.

```bash
# Developer A
python -m orchestrator.main "Add dark mode"
# → run/darkmode-20260113-120000

# Developer B
python -m orchestrator.main "Add mobile menu"
# → run/mobilemenu-20260113-120100

# Both branches visible in GitHub
```

### 3. Iteration Tracking

**Scenario:** Understand what changed between iterations.

```bash
# Run with GitHub enabled
python -m orchestrator.main "Create dashboard"

# View commit history
git log run/dashboard-20260113-123456

# Compare iterations
git diff HEAD~1 HEAD
```

### 4. Code Review

**Scenario:** Review generated code before deploying.

```bash
# Run generates branch
python -m orchestrator.main "Build admin panel"

# Get branch URL from report.json
cat runs/admin-20260113-123456/artifacts/report.json | jq '.github_branch_url'

# Share URL with team for review
# https://github.com/username/template/tree/run/admin-20260113-123456
```

## Security Considerations

### Token Permissions

**Recommended scope:**
- `repo` - For private repositories
- `public_repo` - For public repositories only (more secure)

**Do NOT commit tokens:**
- ❌ Never commit `.env` files
- ❌ Never hardcode tokens
- ✅ Use environment variables
- ✅ Use GitHub Secrets in CI/CD

### Token Storage

```bash
# Good: Environment variable
export GITHUB_TOKEN=ghp_...

# Good: .env file (gitignored)
echo "GITHUB_TOKEN=ghp_..." > .env

# Bad: Hardcoded
github = GitHubClient(token="ghp_hardcoded")  # DON'T DO THIS
```

### Repository Access

- Use personal tokens for personal repos
- Use organization tokens for org repos
- Consider using GitHub App tokens for production
- Rotate tokens regularly

## Troubleshooting

### "GitHub operations disabled"

**Cause:** Missing `GITHUB_TOKEN` or `GITHUB_REPO`

**Solution:**
```bash
# Check environment
echo $GITHUB_TOKEN
echo $GITHUB_REPO

# Set if missing
export GITHUB_TOKEN=ghp_...
export GITHUB_REPO=username/repo
```

### "Failed to create branch"

**Cause:** Branch already exists or insufficient permissions

**Solution:**
```bash
# Check if branch exists
gh api repos/username/repo/git/refs/heads/run/existing-branch

# Delete if needed
gh api -X DELETE repos/username/repo/git/refs/heads/run/existing-branch

# Check token permissions
gh auth status
```

### "Git clone failed"

**Cause:** Invalid token, private repo, or network issue

**Solution:**
```bash
# Test token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Test clone manually
git clone https://$GITHUB_TOKEN@github.com/username/repo.git

# Check repo access
gh repo view username/repo
```

### "Git push failed"

**Cause:** Merge conflicts or protected branch

**Solution:**
```bash
# Check workspace git status
cd workspace
git status
git log --oneline

# Force push if needed (use with caution)
git push -f origin run/branch-name
```

### "No changes to commit"

**Cause:** Patch didn't modify files or files not in workspace

**Solution:**
- This is normal if patch had no effect
- Check patch result logs
- Verify OpenHands actually modified files

## Advanced Usage

### Custom Branch Names

```python
# In your code
run_branch = f"feature/{task.lower().replace(' ', '-')}-{config.run_id}"
github.create_branch(new_branch=run_branch)
```

### Multiple Commits Per Iteration

```python
# After generation
github.commit_and_push(
    workspace_path=workspace,
    message="Initial code generation",
    branch=run_branch
)

# After patch
github.commit_and_push(
    workspace_path=workspace,
    message="Applied fixes from evaluation",
    branch=run_branch
)
```

### Git History Analysis

```bash
# View all run branches
git branch -r | grep run/

# Compare with main
git diff main..run/my-run-123

# Get commit count
git rev-list --count run/my-run-123

# Show file changes
git log --stat run/my-run-123
```

## Comparison: With vs Without GitHub

| Feature | Without GitHub | With GitHub |
|---------|----------------|-------------|
| **Workspace** | Template HTML | Cloned repo |
| **Tracking** | Local only | Git history |
| **Collaboration** | Manual | Automatic |
| **Review** | Local files | GitHub UI |
| **History** | Run artifacts | Git commits |
| **Rollback** | N/A | Git revert |

## Best Practices

### 1. Use Template Repos
Create dedicated template repositories:
```
web-template/
├─ index.html (minimal structure)
├─ styles.css (base styles)
├─ script.js (utilities)
└─ README.md
```

### 2. Clean Branch Names
Use descriptive run IDs:
```python
# Good
run_id = f"{task_slug}-{timestamp}"

# Better
run_id = f"{user}-{task_slug}-{timestamp}"
```

### 3. Commit Granularity
Commit after each meaningful change:
- ✅ After generation
- ✅ After successful patch
- ❌ Not after every file write

### 4. Branch Cleanup
Periodically clean old run branches:
```bash
# List old branches
git branch -r | grep run/

# Delete branches older than 30 days
git branch -r | grep run/ | xargs -I {} git push origin --delete {}
```

## Summary

✅ **Optional integration** - Works with or without GitHub  
✅ **Automatic branching** - One branch per run  
✅ **Auto-commit** - After each successful patch  
✅ **Tracked in reports** - Branch URL in `report.json`  
✅ **Minimal setup** - Just token + repo name  
✅ **Robust fallbacks** - Continues on failure  

**Perfect for template-based development and iteration tracking!**

---

## Quick Commands

```bash
# Enable GitHub integration
export GITHUB_TOKEN=ghp_your_token
export GITHUB_REPO=username/repo
export BASE_BRANCH=main

# Run orchestrator
python -m orchestrator.main "Your task"

# View branch URL in report
cat runs/*/artifacts/report.json | jq '.github_branch_url'

# Browse in GitHub
gh repo view --web --branch run/your-run-id
```

---

**Questions?** See [main README](README.md) or [QUICKSTART](QUICKSTART.md)
