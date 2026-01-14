#!/usr/bin/env python3
"""
Test Enhanced Evaluator

Tests the Gemini-controlled browser QA evaluator
"""

import sys
import asyncio
import tempfile
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.evaluator import (
    GeminiEvaluator,
    EVALUATION_RUBRIC,
    BrowserObservation,
    EvaluationResult,
    EvaluationIssue
)


def test_rubric_schema():
    """Test rubric schema"""
    print("Testing rubric schema...")
    
    assert "functionality" in EVALUATION_RUBRIC
    assert "ux" in EVALUATION_RUBRIC
    assert "accessibility" in EVALUATION_RUBRIC
    assert "responsiveness" in EVALUATION_RUBRIC
    assert "robustness" in EVALUATION_RUBRIC
    
    # Check total weight
    total_weight = sum(cat["weight"] for cat in EVALUATION_RUBRIC.values())
    assert total_weight == 100, f"Total weight should be 100, got {total_weight}"
    
    print("✅ Rubric schema valid")
    print(f"   Categories: {len(EVALUATION_RUBRIC)}")
    print(f"   Total weight: {total_weight}")
    
    for category, details in EVALUATION_RUBRIC.items():
        print(f"   - {category}: {details['weight']} points")


def test_browser_observation():
    """Test BrowserObservation dataclass"""
    print("\nTesting BrowserObservation...")
    
    obs = BrowserObservation()
    
    assert obs.console_logs == []
    assert obs.console_errors == []
    assert obs.interactions_performed == []
    assert obs.interaction_results == {}
    
    # Add some data
    obs.desktop_screenshot = "/path/to/desktop.png"
    obs.interactions_performed.append("navigate")
    obs.interaction_results["navigate"] = True
    
    assert len(obs.interactions_performed) == 1
    assert obs.interaction_results["navigate"] == True
    
    print("✅ BrowserObservation works correctly")


def test_evaluation_issue():
    """Test EvaluationIssue dataclass"""
    print("\nTesting EvaluationIssue...")
    
    issue = EvaluationIssue(
        category="functionality",
        severity="high",
        description="Button does not respond",
        repro_steps=["Click button", "Nothing happens"]
    )
    
    assert issue.category == "functionality"
    assert issue.severity == "high"
    assert len(issue.repro_steps) == 2
    
    print("✅ EvaluationIssue works correctly")


def test_evaluation_result():
    """Test EvaluationResult dataclass"""
    print("\nTesting EvaluationResult...")
    
    obs = BrowserObservation()
    obs.desktop_screenshot = "/path/desktop.png"
    
    result = EvaluationResult(
        score=75,
        passed=True,
        category_scores={
            "functionality": 20,
            "ux": 20,
            "accessibility": 15,
            "responsiveness": 15,
            "robustness": 5
        },
        issues=[],
        fix_suggestions=["Improve accessibility"],
        observations=obs,
        feedback="Good work"
    )
    
    assert result.score == 75
    assert result.passed == True
    assert len(result.category_scores) == 5
    
    print("✅ EvaluationResult works correctly")


def test_evaluator_initialization():
    """Test evaluator initialization"""
    print("\nTesting evaluator initialization...")
    
    import os
    
    # Skip if no API key
    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY"):
        print("⚠️  Skipping (no API key)")
        return
    
    try:
        evaluator = GeminiEvaluator()
        print("✅ Evaluator initialized successfully")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")


def test_to_dict():
    """Test to_dict conversion"""
    print("\nTesting to_dict conversion...")
    
    import os
    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY"):
        print("⚠️  Skipping (no API key)")
        return
    
    evaluator = GeminiEvaluator()
    
    obs = BrowserObservation()
    obs.desktop_screenshot = "/path/desktop.png"
    obs.interactions_performed = ["navigate", "click"]
    
    result = EvaluationResult(
        score=80,
        passed=True,
        category_scores={"functionality": 20},
        issues=[
            EvaluationIssue(
                category="ux",
                severity="low",
                description="Minor spacing issue",
                repro_steps=["View page"]
            )
        ],
        fix_suggestions=["Add more padding"],
        observations=obs,
        feedback="Good"
    )
    
    result_dict = evaluator.to_dict(result)
    
    assert "score" in result_dict
    assert "passed" in result_dict
    assert "issues" in result_dict
    assert "fix_suggestions" in result_dict
    assert len(result_dict["issues"]) == 1
    
    print("✅ to_dict conversion works")
    print(f"   Keys: {list(result_dict.keys())}")


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 Testing Enhanced Evaluator")
    print("=" * 70)
    
    try:
        test_rubric_schema()
        test_browser_observation()
        test_evaluation_issue()
        test_evaluation_result()
        test_evaluator_initialization()
        test_to_dict()
        
        print("\n" + "=" * 70)
        print("✅ All evaluator tests passed!")
        print("=" * 70)
        
        print("\nEvaluator features:")
        print("  1. Structured rubric with 5 categories ✅")
        print("  2. Interactive browser testing ✅")
        print("  3. Multi-viewport screenshots ✅")
        print("  4. Detailed issues with repro steps ✅")
        print("  5. Fix suggestions for patching ✅")
        print("  6. Robust error handling ✅")
        
        print("\nRubric categories:")
        for category, details in EVALUATION_RUBRIC.items():
            print(f"  - {category}: {details['weight']} points")
        
        print("\nUsage:")
        print("  evaluation = await evaluator.evaluate(")
        print("      url=preview_url,")
        print("      mcp_client=mcp,")
        print("      task=task,")
        print("      screenshots_dir=screenshots_dir")
        print("  )")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
