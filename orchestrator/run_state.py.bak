"""
Run State Management

Enhanced with dataclasses for type safety and clean structure
"""

import uuid
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict


@dataclass
class RunConfig:
    """Configuration for a single run"""
    task: str
    max_iterations: int = 3
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    run_id: Optional[str] = None
    
    def __post_init__(self):
        if self.run_id is None:
            self.run_id = self._generate_run_id()
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}_{short_uuid}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['base_dir'] = str(data['base_dir'])
        return data


@dataclass
class IterationResult:
    """Result from a single iteration"""
    iteration: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Generation
    code_generated: Optional[str] = None
    files_generated: Dict[str, str] = field(default_factory=dict)
    generation_time_seconds: float = 0.0
    
    # Testing
    screenshot_path: Optional[str] = None
    page_snapshot: Optional[Dict[str, Any]] = None
    console_errors: List[Dict[str, str]] = field(default_factory=list)
    testing_time_seconds: float = 0.0
    
    # Evaluation
    evaluation: Optional[Dict[str, Any]] = None
    score: int = 0
    passed: bool = False
    feedback: str = ""
    evaluation_time_seconds: float = 0.0
    
    # Total
    total_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['timestamp'] = data['timestamp'].isoformat()
        return data


@dataclass
class RunResult:
    """Complete result from a run"""
    run_id: str
    task: str
    status: str = "running"  # running, completed, failed, cancelled
    
    # Timestamps
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    
    # Iterations
    iterations: List[IterationResult] = field(default_factory=list)
    current_iteration: int = 0
    max_iterations: int = 3
    
    # Final results
    final_score: int = 0
    final_passed: bool = False
    final_feedback: str = ""
    
    # Paths
    workspace_dir: Optional[str] = None
    artifacts_dir: Optional[str] = None
    site_dir: Optional[str] = None
    preview_url: Optional[str] = None
    
    # GitHub info (if enabled)
    github_branch: Optional[str] = None
    github_branch_url: Optional[str] = None
    
    # Error info (if failed)
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    def add_iteration(self, iteration: IterationResult):
        """Add an iteration result"""
        self.iterations.append(iteration)
        self.current_iteration = iteration.iteration
        self.final_score = iteration.score
        self.final_passed = iteration.passed
        self.final_feedback = iteration.feedback
    
    def complete(self, status: str = "completed"):
        """Mark run as complete"""
        self.status = status
        self.end_time = datetime.now()
        self.total_duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def fail(self, error_message: str, traceback: Optional[str] = None):
        """Mark run as failed"""
        self.status = "failed"
        self.error_message = error_message
        self.error_traceback = traceback
        self.complete("failed")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['start_time'] = data['start_time'].isoformat()
        if data['end_time']:
            data['end_time'] = data['end_time'].isoformat()
        
        # Convert iterations
        data['iterations'] = [iter.to_dict() if hasattr(iter, 'to_dict') else iter for iter in data['iterations']]
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class RunManifest:
    """
    Manifest file for run metadata
    
    Records key information about the run for reproducibility and tracking
    """
    
    # Run identification
    run_id: str
    task: str
    
    # Timestamps
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # System versions
    gemini_model_version: str = "gemini-2.0-flash-exp"
    evaluator_model_version: str = "gemini-2.0-flash-exp"
    rubric_version: str = "1.0"
    openhands_mode: str = "mock"
    
    # Run configuration
    max_iterations: int = 2
    iteration_count: int = 0
    
    # Results
    final_score: int = 0
    final_passed: bool = False
    stop_reason: str = "unknown"  # completed, passed, max_iterations, failed, error
    
    # GitHub integration (if enabled)
    github_enabled: bool = False
    github_repo: Optional[str] = None
    github_branch: Optional[str] = None
    github_base_branch: Optional[str] = None
    github_commits: List[Dict[str, str]] = field(default_factory=list)
    
    # Artifacts
    workspace_dir: Optional[str] = None
    artifacts_dir: Optional[str] = None
    site_dir: Optional[str] = None
    preview_url: Optional[str] = None
    
    # Error info (if failed)
    error_message: Optional[str] = None
    
    def add_commit(self, iteration: int, commit_sha: str, commit_url: str):
        """Add a GitHub commit to the manifest"""
        self.github_commits.append({
            "iteration": iteration,
            "commit_sha": commit_sha,
            "commit_url": commit_url,
            "timestamp": datetime.now().isoformat()
        })
    
    def complete(self, stop_reason: str, end_time: Optional[datetime] = None):
        """Mark manifest as complete"""
        self.end_time = end_time or datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.stop_reason = stop_reason
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        data = asdict(self)
        data['start_time'] = data['start_time'].isoformat()
        if data['end_time']:
            data['end_time'] = data['end_time'].isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class RunState:
    """
    Manages state for a single run with full lifecycle support
    """
    
    def __init__(self, config: RunConfig):
        self.config = config
        self.result = RunResult(
            run_id=config.run_id,
            task=config.task,
            max_iterations=config.max_iterations
        )
        
        # Initialize manifest
        self.manifest = RunManifest(
            run_id=config.run_id,
            task=config.task,
            start_time=datetime.now(),
            max_iterations=config.max_iterations,
            openhands_mode=os.getenv("OPENHANDS_MODE", "mock")
        )
        
        # Setup directories
        self.runs_dir = config.base_dir / "runs"
        self.run_dir = self.runs_dir / config.run_id
        
        self.workspace_dir = self.run_dir / "workspace"
        self.artifacts_dir = self.run_dir / "artifacts"
        self.site_dir = self.run_dir / "site"
        
        # Update result with paths
        self.result.workspace_dir = str(self.workspace_dir)
        self.result.artifacts_dir = str(self.artifacts_dir)
        self.result.site_dir = str(self.site_dir)
        
        self._setup_directories()
    
    def _setup_directories(self):
        """Create run directories"""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.site_dir.mkdir(parents=True, exist_ok=True)
    
    def get_preview_url(self, base_url: str = "http://localhost:8080") -> str:
        """Get preview URL for this run"""
        url = f"{base_url}/preview/{self.config.run_id}/"
        self.result.preview_url = url
        return url
    
    def save_state(self) -> Path:
        """Save complete run state"""
        state_file = self.run_dir / "state.json"
        state_file.write_text(self.result.to_json())
        return state_file
    
    def save_report(self) -> Path:
        """Save final report"""
        report_file = self.artifacts_dir / "report.json"
        report_file.write_text(self.result.to_json())
        return report_file
    
    def save_manifest(self) -> Path:
        """Save manifest to JSON"""
        manifest_file = self.artifacts_dir / "manifest.json"
        manifest_file.write_text(self.manifest.to_json())
        return manifest_file
    
    def get_summary(self) -> Dict[str, Any]:
        """Get run summary"""
        return {
            "run_id": self.config.run_id,
            "task": self.config.task,
            "status": self.result.status,
            "iteration": self.result.current_iteration,
            "score": self.result.final_score,
            "passed": self.result.final_passed,
            "preview_url": self.result.preview_url,
            "workspace": str(self.workspace_dir),
            "artifacts": str(self.artifacts_dir),
            "site": str(self.site_dir)
        }
