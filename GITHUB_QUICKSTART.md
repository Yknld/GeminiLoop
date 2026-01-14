# GitHub Integration - Quick Start

Get started with GitHub template branching in 5 minutes.

## Prerequisites

- GitHub account
- Personal access token with `repo` scope
- Template repository (or create one)

## 1. Create GitHub Token

```bash
# Go to: https://github.com/settings/tokens
# Click: Generate new token (classic)
# Select: repo (full control)
# Copy token: ghp_...
```

## 2. Prepare Template Repo

Create a simple template:

```bash
# Create new repo on GitHub
gh repo create username/web-template --public

# Clone it
git clone https://github.com/username/web-template.git
cd web-template

# Add basic template
cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Template</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <h1>Welcome</h1>
        <p>Template ready for GeminiLoop</p>
    </div>
    <script src="script.js"></script>
</body>
</html>
EOF

cat > styles.css << 'EOF'
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui; line-height: 1.6; }
.container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
EOF

cat > script.js << 'EOF'
console.log('Template loaded');
EOF

# Commit and push
git add .
git commit -m "Initial template"
git push
```

## 3. Configure GeminiLoop

```bash
cd /path/to/GeminiLoop

# Set environment variables
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_REPO=username/web-template
export BASE_BRANCH=main

# Or add to .env
cat >> .env << EOF
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=username/web-template
BASE_BRANCH=main
EOF
```

## 4. Run Your First Task

```bash
# Run orchestrator
python -m orchestrator.main "Add a contact form with name, email, and message fields"

# Watch output:
# 🐙 GitHub integration enabled
# 📝 Creating branch: run/contact-20260113-123456
# ✅ Branch created
# 📥 Cloning to workspace...
# ✅ Cloned
# ...
# 🐙 Committing and pushing to GitHub...
# ✅ Pushed to run/contact-20260113-123456
```

## 5. View Results

### In Terminal

```bash
# Get branch URL from report
cat runs/*/artifacts/report.json | jq -r '.github_branch_url'
# → https://github.com/username/web-template/tree/run/contact-20260113-123456
```

### In GitHub

```bash
# Open in browser
gh repo view --web --branch run/contact-20260113-123456

# Or visit directly:
# https://github.com/username/web-template/branches
```

### View Commits

```bash
# Clone the run branch
git clone -b run/contact-20260113-123456 https://github.com/username/web-template.git contact-demo
cd contact-demo

# View commit history
git log --oneline

# Example output:
# a1b2c3d [Iteration 2] Apply OpenHands patch (score: 82/100)
# d4e5f6g [Iteration 1] Apply OpenHands patch (score: 45/100)
# h7i8j9k Initial commit from main
```

## Common Workflows

### 1. Quick Demo

```bash
export GITHUB_TOKEN=ghp_...
export GITHUB_REPO=username/demo-template
python -m orchestrator.main "Create a pricing page with 3 tiers"
```

### 2. Multiple Iterations

```bash
# Run 1
python -m orchestrator.main "Create landing page"
# → run/landing-20260113-120000

# Run 2  
python -m orchestrator.main "Add hero section"
# → run/hero-20260113-120100

# Both branches visible in GitHub
```

### 3. Review Before Deploy

```bash
# Generate code
python -m orchestrator.main "Build dashboard"

# Get branch URL
BRANCH_URL=$(cat runs/*/artifacts/report.json | jq -r '.github_branch_url' | tail -1)

# Share for review
echo "Review at: $BRANCH_URL"

# After approval, merge
gh pr create --base main --head run/dashboard-... --title "Add dashboard"
```

### 4. Local Testing + GitHub

```bash
# Run with GitHub enabled
export GITHUB_TOKEN=ghp_...
python -m orchestrator.main "Create quiz app"

# Test locally
open runs/quiz-*/artifacts/view.html

# If good, push exists in GitHub
# If bad, branch is still there for debugging
```

## Troubleshooting

### "GitHub operations disabled"

```bash
# Check environment
echo $GITHUB_TOKEN
echo $GITHUB_REPO

# Should output your values
# If empty, set them:
export GITHUB_TOKEN=ghp_...
export GITHUB_REPO=username/repo
```

### "Failed to create branch"

```bash
# Branch might already exist
# List all run branches
gh api repos/username/repo/git/refs/heads/run | jq -r '.[] | .ref'

# Delete old branch if needed
gh api -X DELETE repos/username/repo/git/refs/heads/run/old-branch-name
```

### "Clone failed"

```bash
# Test token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
# Should return your user info

# Test repo access
gh repo view username/repo
# Should show repo info

# Check repo exists
gh repo list username
```

## Tips

### 1. Organize Branches

```bash
# Use prefixes for different types
# For template iterations:
export GITHUB_REPO=username/template

# For feature development:
export GITHUB_REPO=username/features
```

### 2. Cleanup Old Branches

```bash
# List branches older than 7 days
gh api repos/username/repo/branches | jq -r '.[] | select(.name | startswith("run/")) | .name'

# Delete old branches (be careful!)
for branch in $(gh api repos/username/repo/branches | jq -r '.[] | select(.name | startswith("run/")) | .name'); do
  echo "Deleting $branch"
  gh api -X DELETE repos/username/repo/git/refs/heads/$branch
done
```

### 3. Branch Protection

```bash
# Protect main branch
gh api repos/username/repo/branches/main/protection \
  -X PUT \
  -f 'required_status_checks[strict]=true' \
  -f 'enforce_admins=true' \
  -f 'required_pull_request_reviews[required_approving_review_count]=1'

# Run branches won't be protected
```

### 4. Private Repos

```bash
# For private repos, ensure token has 'repo' scope
# Public repos only need 'public_repo' scope

# Test access
gh repo view username/private-repo
```

## Next Steps

1. **Read Full Docs:** [GITHUB_INTEGRATION.md](GITHUB_INTEGRATION.md)
2. **Customize Template:** Add your own base styles and scripts
3. **Create PR Workflow:** Auto-create PRs from run branches
4. **Set Up CI/CD:** Run tests on push to run branches

## Examples

### E-commerce Template

```bash
# Template with product grid
export GITHUB_REPO=username/ecommerce-template

# Generate variations
python -m orchestrator.main "Add shopping cart"
python -m orchestrator.main "Add checkout page"
python -m orchestrator.main "Add product details"
```

### Marketing Pages

```bash
# Template with hero + CTA
export GITHUB_REPO=username/marketing-template

# Generate campaigns
python -m orchestrator.main "Create webinar landing page"
python -m orchestrator.main "Create ebook download page"
```

### Documentation Sites

```bash
# Template with sidebar + content
export GITHUB_REPO=username/docs-template

# Generate docs
python -m orchestrator.main "Add API reference page"
python -m orchestrator.main "Add quick start guide"
```

## Summary

✅ **5-minute setup** - Token + repo + run  
✅ **Automatic branching** - One branch per run  
✅ **Full history** - All iterations tracked  
✅ **GitHub UI** - View diffs, commits, files  
✅ **Team collaboration** - Share branch URLs  

**You're ready to use GitHub integration!** 🎉

---

**Questions?** See:
- [GITHUB_INTEGRATION.md](GITHUB_INTEGRATION.md) - Complete guide
- [GITHUB_SUMMARY.md](GITHUB_SUMMARY.md) - Implementation details
- [README.md](README.md) - Main documentation
