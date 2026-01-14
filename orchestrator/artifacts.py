"""
Artifacts Manager

Structured helpers for saving and managing run artifacts
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class ArtifactsManager:
    """
    Manages artifacts for a run
    
    Provides structured methods to save screenshots, logs, evaluations, etc.
    """
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Track all artifacts
        self.manifest: Dict[str, List[Dict[str, Any]]] = {
            "screenshots": [],
            "evaluations": [],
            "logs": [],
            "files": [],
            "reports": []
        }
        self.manifest_file = self.artifacts_dir / "manifest.json"
    
    def save_screenshot(
        self,
        screenshot_path: str,
        iteration: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Save screenshot artifact
        
        Args:
            screenshot_path: Source screenshot path
            iteration: Iteration number
            metadata: Additional metadata
        
        Returns:
            Path to saved screenshot
        """
        # Copy to artifacts directory with structured name
        filename = f"screenshot_iter_{iteration}.png"
        dest = self.artifacts_dir / filename
        
        # Copy file
        source = Path(screenshot_path)
        if source.exists():
            shutil.copy2(source, dest)
        
        # Update manifest
        artifact = {
            "type": "screenshot",
            "iteration": iteration,
            "filename": filename,
            "path": str(dest),
            "size_bytes": dest.stat().st_size if dest.exists() else 0,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.manifest["screenshots"].append(artifact)
        self._save_manifest()
        
        return dest
    
    def save_evaluation(
        self,
        evaluation: Dict[str, Any],
        iteration: int
    ) -> Path:
        """Save evaluation artifact"""
        filename = f"evaluation_iter_{iteration}.json"
        filepath = self.artifacts_dir / filename
        
        # Write evaluation
        filepath.write_text(json.dumps(evaluation, indent=2))
        
        # Update manifest
        artifact = {
            "type": "evaluation",
            "iteration": iteration,
            "filename": filename,
            "path": str(filepath),
            "score": evaluation.get("score", 0),
            "passed": evaluation.get("passed", False),
            "timestamp": datetime.now().isoformat()
        }
        
        self.manifest["evaluations"].append(artifact)
        self._save_manifest()
        
        return filepath
    
    def save_log(
        self,
        content: str,
        name: str,
        log_type: str = "general"
    ) -> Path:
        """Save log artifact"""
        filename = f"{name}.log"
        filepath = self.artifacts_dir / filename
        
        # Write log
        filepath.write_text(content)
        
        # Update manifest
        artifact = {
            "type": "log",
            "log_type": log_type,
            "filename": filename,
            "path": str(filepath),
            "size_bytes": filepath.stat().st_size,
            "timestamp": datetime.now().isoformat()
        }
        
        self.manifest["logs"].append(artifact)
        self._save_manifest()
        
        return filepath
    
    def save_file(
        self,
        content: str,
        filename: str,
        file_type: str = "code",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Save arbitrary file artifact"""
        filepath = self.artifacts_dir / filename
        
        # Write file
        filepath.write_text(content)
        
        # Update manifest
        artifact = {
            "type": "file",
            "file_type": file_type,
            "filename": filename,
            "path": str(filepath),
            "size_bytes": filepath.stat().st_size,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.manifest["files"].append(artifact)
        self._save_manifest()
        
        return filepath
    
    def save_report(
        self,
        report: Dict[str, Any],
        name: str = "report"
    ) -> Path:
        """Save report artifact"""
        filename = f"{name}.json"
        filepath = self.artifacts_dir / filename
        
        # Write report
        filepath.write_text(json.dumps(report, indent=2))
        
        # Update manifest
        artifact = {
            "type": "report",
            "filename": filename,
            "path": str(filepath),
            "timestamp": datetime.now().isoformat()
        }
        
        self.manifest["reports"].append(artifact)
        self._save_manifest()
        
        return filepath
    
    def get_screenshots(self) -> List[Dict[str, Any]]:
        """Get all screenshot artifacts"""
        return sorted(
            self.manifest["screenshots"],
            key=lambda x: x.get("iteration", 0)
        )
    
    def get_evaluations(self) -> List[Dict[str, Any]]:
        """Get all evaluation artifacts"""
        return sorted(
            self.manifest["evaluations"],
            key=lambda x: x.get("iteration", 0)
        )
    
    def get_latest_screenshot(self) -> Optional[Dict[str, Any]]:
        """Get latest screenshot artifact"""
        screenshots = self.get_screenshots()
        return screenshots[-1] if screenshots else None
    
    def get_latest_evaluation(self) -> Optional[Dict[str, Any]]:
        """Get latest evaluation artifact"""
        evaluations = self.get_evaluations()
        return evaluations[-1] if evaluations else None
    
    def _save_manifest(self):
        """Save manifest to disk"""
        self.manifest_file.write_text(json.dumps(self.manifest, indent=2))
    
    def load_manifest(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load manifest from disk"""
        if self.manifest_file.exists():
            self.manifest = json.loads(self.manifest_file.read_text())
        return self.manifest
    
    def get_summary(self) -> Dict[str, Any]:
        """Get artifacts summary"""
        return {
            "total_artifacts": sum(len(v) for v in self.manifest.values()),
            "screenshots": len(self.manifest["screenshots"]),
            "evaluations": len(self.manifest["evaluations"]),
            "logs": len(self.manifest["logs"]),
            "files": len(self.manifest["files"]),
            "reports": len(self.manifest["reports"]),
            "artifacts_dir": str(self.artifacts_dir)
        }


def create_template_html(task: str) -> str:
    """
    Create a simple HTML template for initial workspace
    
    Args:
        task: Task description to include in template
    
    Returns:
        HTML content
    """
    template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Page</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        .container {{
            background: white;
            border-radius: 16px;
            padding: 48px;
            max-width: 600px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }}
        
        h1 {{
            font-size: 32px;
            margin-bottom: 16px;
            color: #1a202c;
        }}
        
        p {{
            color: #4a5568;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        
        .task {{
            background: #f7fafc;
            border-left: 4px solid #667eea;
            padding: 16px;
            border-radius: 4px;
            text-align: left;
            margin-top: 24px;
        }}
        
        .task strong {{
            color: #667eea;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Generated Page</h1>
        <p>This is the initial template. The AI will generate the actual content based on your task.</p>
        
        <div class="task">
            <strong>Task:</strong><br>
            {task}
        </div>
    </div>
</body>
</html>
"""
    return template
