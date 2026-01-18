"""
Trace Logger

Append-only JSONL trace log for debugging and observability
Each event is a single line JSON object
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum
import threading


class TraceEventType(Enum):
    """Types of trace events"""
    RUN_START = "run_start"
    RUN_END = "run_end"
    ITERATION_START = "iteration_start"
    ITERATION_END = "iteration_end"
    GENERATION_START = "generation_start"
    GENERATION_END = "generation_end"
    TESTING_START = "testing_start"
    TESTING_END = "testing_end"
    EVALUATION_START = "evaluation_start"
    EVALUATION_END = "evaluation_end"
    SCREENSHOT_TAKEN = "screenshot_taken"
    ERROR = "error"
    INFO = "info"
    DEBUG = "debug"


class TraceLogger:
    """
    Append-only JSONL trace logger
    
    Thread-safe writer for structured logging
    """
    
    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._event_count = 0
        
        # Initialize file
        self.trace_file.touch(exist_ok=True)
    
    def log(
        self,
        event_type: TraceEventType,
        data: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        level: str = "info"
    ):
        """
        Log a trace event
        
        Args:
            event_type: Type of event
            data: Additional event data
            message: Human-readable message
            level: Log level (info, warning, error, debug)
        """
        event = {
            "event_id": self._event_count,
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type.value,
            "level": level,
        }
        
        if message:
            event["message"] = message
        
        if data:
            event["data"] = data
        
        with self._lock:
            self._event_count += 1
            with open(self.trace_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
    
    def run_start(self, run_id: str, task: str, config: Dict[str, Any]):
        """Log run start"""
        self.log(
            TraceEventType.RUN_START,
            data={
                "run_id": run_id,
                "task": task,
                "config": config
            },
            message=f"Run started: {run_id}"
        )
    
    def run_end(self, run_id: str, status: str, result: Dict[str, Any]):
        """Log run end"""
        self.log(
            TraceEventType.RUN_END,
            data={
                "run_id": run_id,
                "status": status,
                "result": result
            },
            message=f"Run ended: {status}"
        )
    
    def iteration_start(self, iteration: int, total: int):
        """Log iteration start"""
        self.log(
            TraceEventType.ITERATION_START,
            data={"iteration": iteration, "total": total},
            message=f"Iteration {iteration}/{total} started"
        )
    
    def iteration_end(self, iteration: int, score: int, passed: bool):
        """Log iteration end"""
        self.log(
            TraceEventType.ITERATION_END,
            data={
                "iteration": iteration,
                "score": score,
                "passed": passed
            },
            message=f"Iteration {iteration} ended: score={score}, passed={passed}"
        )
    
    def generation_start(self, task: str):
        """Log code generation start"""
        self.log(
            TraceEventType.GENERATION_START,
            data={"task": task},
            message="Code generation started"
        )
    
    def generation_end(self, files_generated: list, duration: float):
        """Log code generation end"""
        self.log(
            TraceEventType.GENERATION_END,
            data={
                "files_generated": files_generated,
                "duration_seconds": duration
            },
            message=f"Code generation completed: {len(files_generated)} files in {duration:.2f}s"
        )
    
    def testing_start(self, url: str):
        """Log testing start"""
        self.log(
            TraceEventType.TESTING_START,
            data={"url": url},
            message=f"Testing started: {url}"
        )
    
    def testing_end(self, screenshot_path: str, console_errors: int, duration: float):
        """Log testing end"""
        self.log(
            TraceEventType.TESTING_END,
            data={
                "screenshot_path": screenshot_path,
                "console_errors": console_errors,
                "duration_seconds": duration
            },
            message=f"Testing completed: {console_errors} errors in {duration:.2f}s"
        )
    
    def evaluation_start(self, screenshot_path: str):
        """Log evaluation start"""
        self.log(
            TraceEventType.EVALUATION_START,
            data={"screenshot_path": screenshot_path},
            message="Evaluation started"
        )
    
    def evaluation_end(self, score: int, passed: bool, duration: float):
        """Log evaluation end"""
        self.log(
            TraceEventType.EVALUATION_END,
            data={
                "score": score,
                "passed": passed,
                "duration_seconds": duration
            },
            message=f"Evaluation completed: score={score}, passed={passed} in {duration:.2f}s"
        )
    
    def screenshot_taken(self, path: str, size_bytes: int):
        """Log screenshot taken"""
        self.log(
            TraceEventType.SCREENSHOT_TAKEN,
            data={
                "path": path,
                "size_bytes": size_bytes
            },
            message=f"Screenshot saved: {path}"
        )
    
    def error(self, message: str, error_type: str, traceback: Optional[str] = None):
        """Log error"""
        self.log(
            TraceEventType.ERROR,
            data={
                "error_type": error_type,
                "traceback": traceback
            },
            message=message,
            level="error"
        )
    
    def info(self, message: str, data: Optional[Dict[str, Any]] = None):
        """Log info message"""
        self.log(TraceEventType.INFO, data=data, message=message, level="info")
    
    def warning(self, message: str, data: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        self.log(TraceEventType.INFO, data=data, message=message, level="warning")
    
    def debug(self, message: str, data: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        self.log(TraceEventType.DEBUG, data=data, message=message, level="debug")


def read_trace(trace_file: Path) -> list:
    """
    Read and parse trace file
    
    Returns list of events in chronological order
    """
    events = []
    
    if not trace_file.exists():
        return events
    
    with open(trace_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    pass
    
    return events


def get_trace_summary(trace_file: Path) -> Dict[str, Any]:
    """
    Get summary statistics from trace
    """
    events = read_trace(trace_file)
    
    if not events:
        return {"total_events": 0}
    
    summary = {
        "total_events": len(events),
        "event_types": {},
        "errors": [],
        "iterations": 0,
        "start_time": events[0].get("timestamp") if events else None,
        "end_time": events[-1].get("timestamp") if events else None
    }
    
    for event in events:
        event_type = event.get("event_type")
        if event_type:
            summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1
        
        if event.get("level") == "error":
            summary["errors"].append({
                "timestamp": event.get("timestamp"),
                "message": event.get("message"),
                "data": event.get("data")
            })
        
        if event_type == "iteration_start":
            summary["iterations"] += 1
    
    return summary
