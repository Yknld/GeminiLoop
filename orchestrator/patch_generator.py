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
    instructions = _build_instructions(task, feedback, score, issues)
    
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
    
    # Extract issues from categories
    for category_name, category_data in evaluation.items():
        if isinstance(category_data, dict) and "issues" in category_data:
            for issue in category_data["issues"]:
                issues.append({
                    "category": category_name,
                    "issue": issue,
                    "severity": "high" if not category_data.get("passed", False) else "medium"
                })
    
    return issues


def _build_instructions(
    task: str,
    feedback: str,
    score: int,
    issues: List[Dict[str, Any]]
) -> str:
    """Build extremely detailed instructions for OpenHands"""
    
    instructions = f"""CRITICAL TASK: Fix ALL issues to achieve 80+ score

ORIGINAL TASK: {task}
CURRENT SCORE: {score}/100 ❌ UNACCEPTABLE
TARGET SCORE: 80+/100 ✅ REQUIRED

=====================================================
EVALUATION FEEDBACK
=====================================================
{feedback}

=====================================================
SPECIFIC ISSUES THAT MUST BE FIXED
=====================================================
"""
    
    if issues:
        for i, issue in enumerate(issues, 1):
            instructions += f"""
{i}. ISSUE: [{issue['category'].upper()}]
   Problem: {issue['issue']}
   Severity: {issue.get('severity', 'HIGH')}
   Action Required: Fix this immediately
"""
    else:
        instructions += "\n- Multiple quality issues detected\n- See feedback above for details\n"
    
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
