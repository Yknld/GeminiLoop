#!/usr/bin/env python3
"""
Test Complete Run Lifecycle

Verifies all components work together
"""

import asyncio
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.run_state import RunConfig, RunState
from orchestrator.trace import TraceLogger, TraceEventType, read_trace, get_trace_summary
from orchestrator.artifacts import ArtifactsManager, create_template_html


def test_run_config():
    """Test RunConfig"""
    print("Testing RunConfig...")
    
    config = RunConfig(
        task="Test task",
        max_iterations=3
    )
    
    assert config.run_id is not None
    assert config.task == "Test task"
    assert config.max_iterations == 3
    
    # Test serialization
    config_dict = config.to_dict()
    assert "run_id" in config_dict
    assert "task" in config_dict
    
    print("✅ RunConfig test passed")


def test_run_state():
    """Test RunState"""
    print("\nTesting RunState...")
    
    config = RunConfig(task="Test task")
    state = RunState(config)
    
    assert state.workspace_dir.exists()
    assert state.artifacts_dir.exists()
    assert state.site_dir.exists()
    
    # Test saving state
    state_file = state.save_state()
    assert state_file.exists()
    
    # Test report
    report_file = state.save_report()
    assert report_file.exists()
    
    print(f"✅ RunState test passed")
    print(f"   Created directories at: {state.run_dir}")


def test_trace_logger():
    """Test TraceLogger"""
    print("\nTesting TraceLogger...")
    
    import tempfile
    trace_file = Path(tempfile.mktemp(suffix=".jsonl"))
    
    trace = TraceLogger(trace_file)
    
    # Log various events
    trace.run_start("test_run", "Test task", {"max_iterations": 3})
    trace.iteration_start(1, 3)
    trace.generation_start("Test task")
    trace.generation_end(["index.html"], 2.5)
    trace.testing_start("http://localhost:8080")
    trace.screenshot_taken("/path/to/screenshot.png", 12345)
    trace.testing_end("/path/to/screenshot.png", 0, 1.2)
    trace.evaluation_start("/path/to/screenshot.png")
    trace.evaluation_end(85, True, 3.1)
    trace.iteration_end(1, 85, True)
    trace.run_end("test_run", "completed", {"score": 85})
    
    # Read back
    events = read_trace(trace_file)
    assert len(events) > 0
    
    # Get summary
    summary = get_trace_summary(trace_file)
    assert summary["total_events"] > 0
    assert "run_start" in summary["event_types"]
    
    print(f"✅ TraceLogger test passed")
    print(f"   Total events: {summary['total_events']}")
    print(f"   Event types: {list(summary['event_types'].keys())}")
    
    # Cleanup
    trace_file.unlink()


def test_artifacts_manager():
    """Test ArtifactsManager"""
    print("\nTesting ArtifactsManager...")
    
    import tempfile
    artifacts_dir = Path(tempfile.mkdtemp())
    
    artifacts = ArtifactsManager(artifacts_dir)
    
    # Save screenshot
    screenshot_path = artifacts.save_screenshot(
        screenshot_path=__file__,  # Use this file as dummy
        iteration=1,
        metadata={"test": True}
    )
    assert screenshot_path.exists()
    
    # Save evaluation
    evaluation = {
        "score": 85,
        "passed": True,
        "feedback": "Good work"
    }
    eval_path = artifacts.save_evaluation(evaluation, 1)
    assert eval_path.exists()
    
    # Save log
    log_path = artifacts.save_log("Test log content", "test", "general")
    assert log_path.exists()
    
    # Save report
    report_path = artifacts.save_report({"test": True}, "test_report")
    assert report_path.exists()
    
    # Get artifacts
    screenshots = artifacts.get_screenshots()
    assert len(screenshots) == 1
    
    evaluations = artifacts.get_evaluations()
    assert len(evaluations) == 1
    
    # Get summary
    summary = artifacts.get_summary()
    assert summary["total_artifacts"] > 0
    
    print(f"✅ ArtifactsManager test passed")
    print(f"   Total artifacts: {summary['total_artifacts']}")
    print(f"   Manifest location: {artifacts.manifest_file}")
    
    # Cleanup
    import shutil
    shutil.rmtree(artifacts_dir)


def test_template_html():
    """Test HTML template creation"""
    print("\nTesting HTML template...")
    
    html = create_template_html("Create a landing page")
    
    assert "<!DOCTYPE html>" in html
    assert "Create a landing page" in html
    assert "<style>" in html
    
    print("✅ HTML template test passed")


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 Testing Run Lifecycle Components")
    print("=" * 70)
    
    try:
        test_run_config()
        test_run_state()
        test_trace_logger()
        test_artifacts_manager()
        test_template_html()
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        
        print("\nRun lifecycle is ready:")
        print("  1. RunConfig + RunState for state management ✅")
        print("  2. TraceLogger for JSONL append-only logging ✅")
        print("  3. ArtifactsManager for structured artifacts ✅")
        print("  4. Template HTML generation ✅")
        print("\nNext: Run 'python -m orchestrator.main' to test full loop")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
