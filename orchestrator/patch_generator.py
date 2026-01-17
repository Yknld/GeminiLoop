"""
Patch Plan Generator

Creates patch plans from evaluation feedback for OpenHands to apply
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def generate_patch_plan(
    evaluation: Dict[str, Any],
    task: str,
    files_generated: Dict[str, str]
) -> Dict[str, Any]:
    """
    Generate a patch plan from evaluation feedback
    
    Args:
        evaluation: Evaluation result with feedback
        task: Original task description
        files_generated: Dict of filename -> filepath
    
    Returns:
        Patch plan dict for OpenHands
    """
    
    feedback = evaluation.get("feedback", "")
    score = evaluation.get("score", 0)
    issues = extract_issues_from_evaluation(evaluation)
    
    logger.info(f"📝 Generating patch plan from evaluation")
    logger.info(f"   Score: {score}/100")
    logger.info(f"   Issues found: {len(issues)}")
    
    # Build instructions for OpenHands
    instructions = _build_instructions(task, evaluation, issues)
    
    # Determine which files need changes
    files_to_patch = []
    for filename, filepath in files_generated.items():
        file_issues = [i for i in issues if filename in i.get("context", "")]
        
        if file_issues or score < 70:  # Patch if file has issues or overall score is low
            files_to_patch.append({
                "path": filename,
                "action": "modify",
                "description": _generate_file_description(filename, file_issues, feedback),
                "changes": _generate_changes_list(file_issues, feedback)
            })
    
    # If no specific files identified, patch all generated files
    if not files_to_patch and score < 70:
        for filename in files_generated.keys():
            files_to_patch.append({
                "path": filename,
                "action": "modify",
                "description": f"Improve based on evaluation feedback: {feedback[:100]}...",
                "changes": []
            })
    
    patch_plan = {
        "instructions": instructions,
        "files": files_to_patch,
        "original_score": score,
        "issues_count": len(issues)
    }
    
    logger.info(f"   Files to patch: {len(files_to_patch)}")
    
    return patch_plan


def extract_issues_from_evaluation(evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract specific issues from evaluation"""
    
    issues = []
    
    # Debug: Log evaluation structure
    logger.debug(f"Evaluation keys: {list(evaluation.keys())}")
    logger.debug(f"Has 'issues' key: {'issues' in evaluation}")
    if "issues" in evaluation:
        logger.debug(f"Issues type: {type(evaluation['issues'])}, length: {len(evaluation['issues']) if isinstance(evaluation['issues'], list) else 'N/A'}")
    
    # First, extract from issues list if available (preferred)
    if "issues" in evaluation and isinstance(evaluation["issues"], list):
        logger.debug(f"Extracting from evaluation['issues'] list ({len(evaluation['issues'])} items)")
        for issue_data in evaluation["issues"]:
            if isinstance(issue_data, dict):
                issue_desc = issue_data.get("description", "")
                if issue_desc:  # Only add if description exists
                    issues.append({
                        "category": issue_data.get("category", "unknown"),
                        "issue": issue_desc,
                        "severity": issue_data.get("severity", "medium"),
                        "repro_steps": issue_data.get("repro_steps", [])
                    })
                    logger.debug(f"  Extracted issue: {issue_desc[:50]}...")
    
    # Also extract issues from category data (fallback)
    for category_name, category_data in evaluation.items():
        if isinstance(category_data, dict) and "issues" in category_data:
            for issue in category_data["issues"]:
                issue_str = issue if isinstance(issue, str) else str(issue)
                # Avoid duplicates
                if issue_str and not any(i.get("issue") == issue_str for i in issues):
                    issues.append({
                        "category": category_name,
                        "issue": issue_str,
                        "severity": "high" if not category_data.get("passed", False) else "medium"
                    })
    
    logger.debug(f"Total issues extracted: {len(issues)}")
    return issues


def _build_instructions(
    task: str,
    evaluation: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> str:
    """Build extremely detailed instructions for OpenHands"""
    
    feedback = evaluation.get("feedback", "")
    score = evaluation.get("score", 0)
    category_scores = evaluation.get("category_scores", {})
    detailed_issues = evaluation.get("issues", [])
    fix_suggestions = evaluation.get("fix_suggestions", [])
    
    # Build category scores breakdown
    category_breakdown = ""
    if category_scores:
        category_breakdown = "\nCATEGORY SCORES BREAKDOWN:\n"
        max_scores = {
            "functionality": 25,
            "ux": 25,
            "accessibility": 20,
            "responsiveness": 20,
            "robustness": 10
        }
        for category, cat_score in category_scores.items():
            max_score = max_scores.get(category, 100)
            percentage = (cat_score / max_score * 100) if max_score > 0 else 0
            status = "✅" if percentage >= 70 else "❌"
            category_breakdown += f"  {status} {category.replace('_', ' ').title()}: {cat_score}/{max_score} ({percentage:.0f}%)\n"
    
    instructions = f"""CRITICAL TASK: Fix ALL issues to achieve 80+ score

ORIGINAL TASK: {task}
CURRENT SCORE: {score}/100 ❌ UNACCEPTABLE
TARGET SCORE: 80+/100 ✅ REQUIRED
{category_breakdown}
=====================================================
EVALUATION FEEDBACK SUMMARY
=====================================================
{feedback}

=====================================================
KEY ISSUES THAT MUST BE FIXED ({len(detailed_issues)} total)
=====================================================
"""
    
    if detailed_issues:
        # Sort by severity: critical > high > medium > low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_issues = sorted(detailed_issues, key=lambda x: severity_order.get(x.get("severity", "medium"), 2))
        
        for i, issue in enumerate(sorted_issues, 1):
            severity = issue.get("severity", "medium")
            category = issue.get("category", "unknown")
            description = issue.get("description", "")
            repro_steps = issue.get("repro_steps", [])
            
            instructions += f"""
{i}. [{severity.upper()}] {category.replace('_', ' ').title()} Issue:
   Description: {description}
"""
            if repro_steps:
                instructions += "   Reproduction Steps:\n"
                for step_num, step in enumerate(repro_steps, 1):
                    instructions += f"      {step_num}. {step}\n"
            instructions += "   Action Required: Fix this issue completely\n"
    elif issues:
        # Fallback to extracted issues if detailed_issues not available
        for i, issue in enumerate(issues, 1):
            instructions += f"""
{i}. ISSUE: [{issue['category'].upper()}]
   Problem: {issue['issue']}
   Severity: {issue.get('severity', 'HIGH')}
   Action Required: Fix this immediately
"""
    else:
        instructions += "\n- Multiple quality issues detected\n- See feedback above for details\n"
    
    if fix_suggestions:
        instructions += f"""
=====================================================
FIX SUGGESTIONS ({len(fix_suggestions)} total)
=====================================================
"""
        for i, suggestion in enumerate(fix_suggestions, 1):
            instructions += f"{i}. {suggestion}\n"
    
    instructions += """
=====================================================
DETAILED REQUIREMENTS FOR FIXES
=====================================================

1. FUNCTIONALITY (CRITICAL):
   - Add missing JavaScript event handlers
   - Implement ALL form submission logic
   - Make EVERY button work (no non-functional UI)
   - Add proper validation and error messages
   - Show success/feedback after user actions
   - Test that clicking every element does something
   
2. STYLING & VISUAL DESIGN (HIGH PRIORITY):
   - Fix color contrast to meet WCAG AA (4.5:1 minimum)
   - Use professional color palette:
     * Primary: #667eea (purple-blue)
     * Success: #48bb78 (green)
     * Error: #e53e3e (red)
     * Text: #2d3748 (dark gray)
     * Background: #f7fafc (light gray)
   - Add proper spacing (8px grid: 8, 16, 24, 32, 40px)
   - Improve typography:
     * Headings: font-weight 700
     * Body: font-weight 400
     * Line-height: 1.6 for readability
   - Add hover effects on ALL interactive elements
   - Add focus indicators (outline: 2px solid)
   
3. RESPONSIVE DESIGN (HIGH PRIORITY):
   - Test at 375px mobile width
   - Test at 768px tablet width  
   - Test at 1440px desktop width
   - Use CSS media queries
   - Stack elements vertically on mobile
   - Increase tap target sizes to 44px minimum
   - Prevent horizontal scrolling
   
4. ACCESSIBILITY (REQUIRED):
   - Use semantic HTML (header, main, nav, section, article)
   - Add ARIA labels to interactive elements
   - Ensure keyboard tab order is logical
   - Add role attributes where needed
   - Make focus indicators clearly visible
   
5. CODE QUALITY (REQUIRED):
   - Remove ALL console errors
   - Add comments explaining functionality
   - Use modern JavaScript (ES6+)
   - Keep code organized and readable
   - Validate HTML and CSS

=====================================================
SUCCESS CRITERIA
=====================================================
✅ All buttons and forms work perfectly
✅ Color contrast passes WCAG AA
✅ Looks good on mobile, tablet, and desktop
✅ No console errors
✅ Professional, polished appearance
✅ Score improves to 80+/100

APPLY ALL FIXES NOW. BE THOROUGH AND COMPLETE.
"""
    
    return instructions


def _generate_file_description(
    filename: str,
    file_issues: List[Dict[str, Any]],
    feedback: str
) -> str:
    """Generate description for file changes"""
    
    if file_issues:
        issues_str = ", ".join([i["issue"][:50] for i in file_issues[:3]])
        return f"Fix issues: {issues_str}"
    else:
        return f"Improve based on feedback: {feedback[:80]}..."


def _generate_changes_list(
    issues: List[Dict[str, Any]],
    feedback: str
) -> List[str]:
    """Generate specific changes list from issues"""
    
    changes = []
    
    for issue in issues[:5]:  # Limit to top 5 issues
        issue_text = issue.get("issue", "")
        category = issue.get("category", "")
        
        # Convert issue to actionable change
        if "button" in issue_text.lower():
            changes.append("Improve button styling with better colors, padding, and hover effects")
        
        if "color" in issue_text.lower() or "visual" in category.lower():
            changes.append("Enhance color scheme for better visual hierarchy")
        
        if "spacing" in issue_text.lower() or "padding" in issue_text.lower():
            changes.append("Adjust spacing and padding for better layout")
        
        if "font" in issue_text.lower():
            changes.append("Improve typography with better font sizes and weights")
        
        if "error" in issue_text.lower() or category == "errors":
            changes.append("Fix console errors and JavaScript issues")
        
        if "responsive" in issue_text.lower():
            changes.append("Improve responsive design for mobile devices")
    
    # Add generic changes if no specific ones identified
    if not changes:
        if "visual" in feedback.lower() or "design" in feedback.lower():
            changes.append("Improve overall visual design and polish")
        if "functionality" in feedback.lower() or "work" in feedback.lower():
            changes.append("Ensure all functionality works as expected")
        if not changes:
            changes.append("General improvements based on evaluation feedback")
    
    return changes


def create_simple_patch_plan(
    feedback: str,
    filename: str = "index.html"
) -> Dict[str, Any]:
    """
    Create a simple patch plan for quick testing
    
    Args:
        feedback: Evaluation feedback
        filename: File to patch
    
    Returns:
        Simple patch plan
    """
    
    return {
        "instructions": f"Improve the code based on this feedback: {feedback}",
        "files": [
            {
                "path": filename,
                "action": "modify",
                "description": f"Apply improvements: {feedback[:100]}",
                "changes": [
                    "Improve visual design",
                    "Fix any issues",
                    "Polish user experience"
                ]
            }
        ]
    }
