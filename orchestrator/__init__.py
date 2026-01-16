"""
GeminiLoop Orchestrator

Main orchestration package for code generation, evaluation, and iteration loop.
"""

from .paths import (
    PathConfig,
    get_path_config,
    create_path_config,
    reset_path_config
)

from .preview_server import (
    PreviewServer,
    get_preview_server,
    stop_preview_server,
    reset_preview_server
)

from .run_state import (
    RunConfig,
    RunState,
    IterationResult,
    RunResult,
    RunManifest
)

from .bootstrap import (
    TemplateConfig,
    TemplateBootstrap,
    bootstrap_from_template
)

from .openhands_client import (
    OpenHandsClient,
    LocalSubprocessOpenHandsClient,
    MockOpenHandsClient,
    get_openhands_client
)

# Optional import - may fail if google-generativeai not installed
try:
    from .evaluator import (
        GeminiEvaluator,
        EvaluationResult,
        EvaluationIssue,
        BrowserObservation,
        EVALUATOR_MODEL_VERSION,
        RUBRIC_VERSION
    )
    _evaluator_available = True
except ImportError:
    # Evaluator not available - that's OK for path/preview testing
    GeminiEvaluator = None
    EvaluationResult = None
    EvaluationIssue = None
    BrowserObservation = None
    EVALUATOR_MODEL_VERSION = None
    RUBRIC_VERSION = None
    _evaluator_available = False

__all__ = [
    # Path configuration
    'PathConfig',
    'get_path_config',
    'create_path_config',
    'reset_path_config',
    
    # Preview server
    'PreviewServer',
    'get_preview_server',
    'stop_preview_server',
    'reset_preview_server',
    
    # Run state
    'RunConfig',
    'RunState',
    'IterationResult',
    'RunResult',
    'RunManifest',
    
    # Template bootstrap
    'TemplateConfig',
    'TemplateBootstrap',
    'bootstrap_from_template',
    
    # OpenHands client
    'OpenHandsClient',
    'LocalSubprocessOpenHandsClient',
    'MockOpenHandsClient',
    'get_openhands_client',
    
    # Evaluator
    'GeminiEvaluator',
    'EvaluationResult',
    'EvaluationIssue',
    'BrowserObservation',
    'EVALUATOR_MODEL_VERSION',
    'RUBRIC_VERSION',
]
