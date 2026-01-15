"""
Event emitter for live monitoring
Broadcasts events to connected clients via the live server
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

# Global event queue (will be set by live_server if running)
_event_queue: Optional[asyncio.Queue] = None
_broadcast_queues: list = []


def set_event_queue(queue: asyncio.Queue):
    """Set the global event queue for broadcasting"""
    global _event_queue
    _event_queue = queue


def add_broadcast_queue(queue: asyncio.Queue):
    """Add a queue to broadcast to"""
    _broadcast_queues.append(queue)


def remove_broadcast_queue(queue: asyncio.Queue):
    """Remove a broadcast queue"""
    if queue in _broadcast_queues:
        _broadcast_queues.remove(queue)


def emit_event(event_type: str, data: Dict[str, Any]):
    """
    Emit an event to all connected clients
    
    Args:
        event_type: Type of event (run_start, iteration_start, etc.)
        data: Event data
    """
    event = {
        "type": event_type,
        "data": {
            **data,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # Broadcast to all queues
    for queue in _broadcast_queues:
        try:
            queue.put_nowait(event)
        except:
            pass
    
    # Also send to main queue if set
    if _event_queue:
        try:
            _event_queue.put_nowait(event)
        except:
            pass


# Convenience functions for common events

def emit_run_start(run_id: str, task: str):
    """Emit run start event"""
    emit_event("run_start", {
        "run_id": run_id,
        "task": task
    })


def emit_iteration_start(iteration: int):
    """Emit iteration start event"""
    emit_event("iteration_start", {
        "iteration": iteration
    })


def emit_code_generated(files: list, method: str = "openhands"):
    """Emit code generation event"""
    emit_event("code_generated", {
        "files": files,
        "method": method
    })


def emit_evaluation(iteration: int, score: int, passed: bool, feedback: str):
    """Emit evaluation event"""
    emit_event("evaluation", {
        "iteration": iteration,
        "score": score,
        "passed": passed,
        "feedback": feedback
    })


def emit_patch_applied(files: list):
    """Emit patch applied event"""
    emit_event("patch_applied", {
        "files": files
    })


def emit_run_complete(run_id: str, final_score: int, passed: bool, iterations: int):
    """Emit run complete event"""
    emit_event("run_complete", {
        "run_id": run_id,
        "final_score": final_score,
        "passed": passed,
        "iterations": iterations
    })


def emit_log(message: str, level: str = "INFO"):
    """Emit a log message"""
    emit_event("log", {
        "message": message,
        "level": level
    })


def emit_screenshot(iteration: int, view: str, screenshot_b64: str):
    """Emit screenshot event"""
    emit_event("screenshot", {
        "iteration": iteration,
        "view": view,
        "screenshot": screenshot_b64
    })
