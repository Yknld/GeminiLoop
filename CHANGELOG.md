# Changelog

All notable changes to GeminiLoop will be documented in this file.

## [1.0.0] - 2026-01-13

### Added - Complete Run Lifecycle

#### State Management
- **RunConfig dataclass**: Type-safe run configuration
  - `task`, `max_iterations`, `base_dir`, `run_id`
- **IterationResult dataclass**: Per-iteration results tracking
  - Code generation, testing, evaluation data
  - Timing information for each phase
- **RunResult dataclass**: Complete run results
  - Status tracking (running, completed, failed)
  - Iteration history
  - Final scores and feedback
- **RunState class**: Main state management
  - Directory setup (workspace, artifacts, site)
  - State persistence (state.json, report.json)

#### Trace Logging
- **TraceLogger**: Append-only JSONL event logging
  - Thread-safe writes
  - Event types: run, iteration, generation, testing, evaluation
  - Structured event data with timestamps
  - Helper methods for common events
- **Trace utilities**:
  - `read_trace()`: Parse trace file
  - `get_trace_summary()`: Statistics and summary

#### Artifacts Management
- **ArtifactsManager**: Structured artifact handling
  - Screenshot management with iteration tracking
  - Evaluation storage
  - Log file management
  - General file artifacts
  - Report generation
- **Artifact manifest**: JSON manifest of all artifacts
  - Automatic tracking and metadata
  - Easy artifact retrieval

#### Orchestrator Enhancements
- Complete lifecycle implementation in `main.py`:
  - Phase 0: Workspace setup with template HTML
  - Phase 1: Code generation with Gemini
  - Phase 2: Browser testing with MCP
  - Phase 3: Quality evaluation with Gemini Vision
  - Automatic iteration until passing or max iterations
- Integration with all new components:
  - TraceLogger for observability
  - ArtifactsManager for structured storage
  - Enhanced error handling and reporting

#### Visualization
- **view.html**: Auto-generated results viewer
  - Shows all iterations with screenshots
  - Displays scores and pass/fail status
  - Links to preview, report, and trace
  - Clean, modern UI
  - Embedded JavaScript for report loading

#### Template System
- **create_template_html()**: Initial workspace template
  - Beautiful gradient design
  - Task description display
  - Placeholder for generated content

#### Testing
- **test_lifecycle.py**: Comprehensive lifecycle tests
  - RunConfig/RunState testing
  - TraceLogger verification
  - ArtifactsManager validation
  - Template HTML generation

#### Documentation
- **ARCHITECTURE.md**: Complete architecture documentation
  - Component descriptions
  - Data flow diagrams
  - Folder structure
  - Extension points
- **QUICKSTART.md**: 5-minute setup guide
- **Makefile**: Common task automation

### Folder Structure

```
/runs/<run_id>/
  ├── workspace/              # Generated code
  │   └── index.html
  ├── artifacts/              # Run artifacts
  │   ├── trace.jsonl        # Event log
  │   ├── manifest.json      # Artifact tracking
  │   ├── report.json        # Final report
  │   ├── view.html          # Results viewer
  │   ├── screenshot_iter_*.png
  │   └── evaluation_iter_*.json
  ├── site/                  # Served files
  │   └── index.html
  └── state.json             # Complete state
```

### Technical Details

- **Language**: Python 3.11+, Node.js 18+
- **Dependencies**: 
  - google-generativeai
  - playwright
  - fastapi
  - pydantic (dataclasses)
- **Protocol**: JSON-RPC 2.0 over stdio (MCP)
- **Logging**: JSONL append-only format
- **Storage**: File-based with JSON manifests

### Example Usage

```bash
# Setup
make setup
cp .env.example .env
# Edit .env with API key

# Run
python -m orchestrator.main "Create a landing page"

# View results
open runs/<run_id>/artifacts/view.html

# Start preview server
make preview

# Test
make test
```

### Breaking Changes

None - this is the initial release with complete lifecycle support.

### Migration Guide

If you were using the previous simple version:
- Old: Basic RunState with manual state tracking
- New: Comprehensive dataclasses with automatic tracking
- Old: No trace logging
- New: Complete JSONL trace with all events
- Old: Manual artifact management
- New: ArtifactsManager with manifest

## [0.1.0] - 2026-01-13 (Initial MVP)

### Added
- Basic orchestrator structure
- Simple run state management
- Gemini code generation
- Gemini evaluation
- Playwright MCP integration
- Preview server
- RunPod deployment files
