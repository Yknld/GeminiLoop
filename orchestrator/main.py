#!/usr/bin/env python3
"""
GeminiLoop Orchestrator - Main Entry Point

Complete run lifecycle with tracing, artifacts, and reporting
"""

import asyncio
import sys
import os
import logging
import time
import json
import traceback as tb
from pathlib import Path
from datetime import datetime

from .run_state import RunConfig, RunState, IterationResult
from .trace import TraceLogger, TraceEventType
from .artifacts import ArtifactsManager, create_template_html
from .evaluator import GeminiEvaluator, EVALUATOR_MODEL_VERSION, RUBRIC_VERSION
from .agentic_evaluator import AgenticEvaluator
from .mcp_real_client import PlaywrightMCPClient
from .openhands_client import get_openhands_client
from .patch_generator import generate_patch_plan
from .github_client import get_github_client
from .paths import get_path_config, PathConfig
from .preview_server import get_preview_server, stop_preview_server
from .bootstrap import bootstrap_from_template, TemplateConfig
from .planner import Planner
from .youtube_finder import YouTubeFinder
from . import events  # Live monitoring events

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_loop(task: str, max_iterations: int = 5, base_dir: Path = None, custom_notes: str = None) -> RunState:
    """
    Main orchestration loop with complete lifecycle
    
    Args:
        task: What to build
        max_iterations: Maximum number of iterations
        base_dir: Base directory for runs
        custom_notes: Optional custom prompt/notes to use instead of planner-generated prompt
    
    Returns:
        RunState with complete results
    """
    # Ensure os module is accessible (workaround for potential scoping issues)
    import os as _os_module
    os = _os_module
    
    print("🚀 GeminiLoop Orchestrator")
    print("=" * 70)
    print(f"Task: {task}")
    print("=" * 70)
    
    # Initialize path configuration (single source of truth)
    path_config = get_path_config(base_dir)
    
    # Create run configuration
    config = RunConfig(
        task=task,
        max_iterations=max_iterations,
        base_dir=base_dir or Path.cwd()
    )
    
    # Initialize run state
    state = RunState(config)
    
    # Initialize trace logger
    trace = TraceLogger(state.artifacts_dir / "trace.jsonl")
    
    # Initialize artifacts manager
    artifacts = ArtifactsManager(state.artifacts_dir)
    
    # Log run start
    trace.run_start(
        run_id=config.run_id,
        task=task,
        config=config.to_dict()
    )
    
    print(f"\n📁 Run ID: {config.run_id}")
    print(f"   Workspace: {state.workspace_dir}")
    print(f"   Artifacts: {state.artifacts_dir}")
    print(f"   Site: {state.site_dir}")
    print(f"   Preview: {state.get_preview_url()}")
    print(f"   Trace: {state.artifacts_dir / 'trace.jsonl'}")
    print(f"   Manifest: {state.artifacts_dir / 'manifest.json'}")
    
    # Emit run start event for live monitoring
    events.emit_run_start(config.run_id, task)
    
    # Start HTTP preview server (replaces file:// URLs)
    print(f"\n🌐 Starting HTTP preview server...")
    preview_server = get_preview_server(
        serve_dir=path_config.project_root,
        host=path_config.preview_host,
        port=path_config.preview_port
    )
    print(f"✅ Preview server running at: {preview_server.url}")
    print(f"   Serving from: {path_config.project_root}")
    
    # Initialize clients
    # Choose evaluator: agentic (Gemini controls browser) or scripted (fixed tests)
    use_agentic = os.getenv("AGENTIC_EVAL", "true").lower() in ("true", "1", "yes")
    if use_agentic:
        # Default to 30 steps (can finish early via finish_exploration tool)
        max_steps = int(os.getenv("AGENTIC_MAX_STEPS", "30"))
        evaluator = AgenticEvaluator(max_exploration_steps=max_steps)
        print(f"🤖 Using Agentic Evaluator (Gemini controls browser, max {max_steps} steps)")
        print(f"   Note: Evaluator maintains full conversation history and can finish early if done")
    else:
        evaluator = GeminiEvaluator()
        print(f"📋 Using Scripted Evaluator (fixed test checklist)")
    
    openhands = get_openhands_client(state.artifacts_dir)
    github = get_github_client()
    mcp = None
    
    try:
        # Phase 0a: Bootstrap from template repository (if configured)
        print(f"\n{'=' * 70}")
        print(f"📋 Phase 0a: Template Bootstrap")
        print(f"{'=' * 70}")
        
        template_config = TemplateConfig.from_env()
        bootstrap_result = bootstrap_from_template(
            workspace_root=path_config.workspace_root,
            config=template_config
        )
        
        if bootstrap_result.get("success"):
            print(f"✅ Template bootstrap successful")
            print(f"   Repository: {bootstrap_result['repo_url']}")
            print(f"   Ref: {bootstrap_result['ref']}")
            print(f"   Files: {bootstrap_result['files_count']}")
            
            # Update manifest
            state.manifest.github_enabled = True
            state.manifest.github_repo = bootstrap_result['repo_url']
            
            trace.info("Template bootstrap successful", data=bootstrap_result)
        elif bootstrap_result.get("enabled"):
            print(f"⚠️  Template bootstrap failed")
            print(f"   Error: {bootstrap_result.get('error')}")
            trace.warning("Template bootstrap failed", data=bootstrap_result)
        else:
            print(f"ℹ️  Template bootstrap disabled")
            trace.info("Template bootstrap disabled")
        
        # Phase 0b: Setup workspace with template (or GitHub clone)
        print(f"\n{'=' * 70}")
        print(f"📋 Phase 0b: Workspace Setup (Legacy)")
        print(f"{'=' * 70}")
        
        # Check if GitHub is enabled (legacy - prefer template bootstrap above)
        # Skip if template bootstrap succeeded
        if github.is_enabled() and not bootstrap_result.get("success"):
            print(f"\n🐙 GitHub integration enabled")
            print(f"   Repo: {github.repo_name}")
            print(f"   Base branch: {github.base_branch}")
            
            # Update manifest
            state.manifest.github_enabled = True
            state.manifest.github_repo = github.repo_name
            state.manifest.github_base_branch = github.base_branch
            
            # Create branch for this run
            run_branch = f"run/{config.run_id}"
            print(f"\n📝 Creating branch: {run_branch}")
            
            branch_result = github.create_branch(
                new_branch=run_branch,
                base_branch=github.base_branch
            )
            
            if branch_result["success"]:
                print(f"✅ Branch created: {run_branch}")
                trace.info("GitHub branch created", data=branch_result)
            else:
                print(f"⚠️  Branch creation failed: {branch_result['message']}")
                trace.warning("GitHub branch creation failed", data=branch_result)
            
            # Clone branch to workspace
            print(f"\n📥 Cloning {run_branch} to workspace...")
            
            clone_result = github.clone_branch_to_workspace(
                branch=run_branch,
                workspace_path=state.workspace_dir
            )
            
            if clone_result["success"]:
                print(f"✅ Cloned to: {state.workspace_dir}")
                trace.info("GitHub branch cloned", data=clone_result)
                
                # Copy cloned files to site
                print(f"\n📋 Copying files to site directory...")
                import shutil
                for item in state.workspace_dir.iterdir():
                    if item.name != ".git":
                        if item.is_file():
                            shutil.copy2(item, state.site_dir / item.name)
                        elif item.is_dir():
                            shutil.copytree(item, state.site_dir / item.name, dirs_exist_ok=True)
                print(f"✅ Files copied to site")
                
                # Store branch URL in state and manifest
                state.result.github_branch = run_branch
                state.result.github_branch_url = github.get_branch_url(run_branch)
                state.manifest.github_branch = run_branch
            else:
                print(f"⚠️  Clone failed: {clone_result['message']}")
                print(f"   Starting with empty workspace (OpenHands will create files)")
                trace.warning("GitHub clone failed, using empty workspace", data=clone_result)
        elif not bootstrap_result.get("success"):
            print(f"\nℹ️  Neither template nor GitHub bootstrap succeeded")
            print(f"   OpenHands will create files from scratch")
            trace.info("Starting with empty workspace (OpenHands will create files)")
        
        # Phase 0c: Planning with Gemini (or use custom notes)
        # Do this BEFORE MCP connection since planner doesn't need browser
        print(f"\n{'=' * 70}")
        
        # Phase 0c: Planning with Gemini (always use planner)
        # Find YouTube videos before planning
        print(f"\n{'=' * 70}")
        print(f"🎥 Phase 0b: Finding YouTube videos")
        print(f"{'=' * 70}")
        
        youtube_videos = []
        try:
            youtube_finder = YouTubeFinder()
            youtube_videos = youtube_finder.find_videos_for_content(
                user_requirements=task,
                custom_notes=custom_notes,
                count=5
            )
            
            if youtube_videos:
                print(f"✅ Found {len(youtube_videos)} YouTube videos")
                # Save videos to artifacts
                videos_file = state.artifacts_dir / "youtube_videos.json"
                with open(videos_file, 'w') as f:
                    json.dump(youtube_videos, f, indent=2)
                print(f"💾 Videos saved to: {videos_file}")
            else:
                print("⚠️  No YouTube videos found")
        except Exception as e:
            print(f"⚠️  Error finding YouTube videos: {e}")
            print("   Continuing without YouTube videos...")
            youtube_videos = []
        
        # If custom_notes provided, planner uses them to generate prompt
        # If not, planner uses task description
        print(f"\n{'=' * 70}")
        if custom_notes:
            print(f"🧠 Phase 0c: Planning with Gemini (using custom notes)")
            print(f"{'=' * 70}")
            
            # Save custom notes to artifacts for reference
            notes_file = state.artifacts_dir / "custom_notes.txt"
            notes_file.write_text(custom_notes, encoding='utf-8')
            print(f"📝 Custom notes saved: {notes_file}")
            print(f"   Notes length: {len(custom_notes)} characters")
        else:
            print(f"🧠 Phase 0c: Planning with Gemini")
            print(f"{'=' * 70}")
        
        # Always use planner - it will use custom_notes if provided
        planner = Planner()
        plan = planner.generate_openhands_prompt(
            user_requirements=task,
            custom_notes=custom_notes,
            youtube_videos=youtube_videos if youtube_videos else None
        )
        
        # Save plan to artifacts
        planner.save_plan(plan, state.artifacts_dir)
        
        # Store generated prompt for OpenHands
        openhands_prompt = plan['prompt']
        
        print(f"✅ Planning complete")
        print(f"   Generated prompt: {len(openhands_prompt)} characters")
        if plan.get('thinking'):
            print(f"   Thinking process: {len(plan['thinking'])} characters")
        
        trace.info("Planning complete", data={
            'prompt_length': len(openhands_prompt),
            'has_thinking': plan.get('thinking') is not None,
            'model': plan['metadata']['model'],
            'used_custom_notes': custom_notes is not None
        })
        
        # Start MCP client
        print(f"\n🌐 Starting Playwright MCP server...")
        mcp = PlaywrightMCPClient()
        await mcp.connect()
        print(f"✅ MCP server connected")
        
        # Main iteration loop
        for iteration in range(1, max_iterations + 1):
            iter_result = IterationResult(iteration=iteration)
            iter_start_time = time.time()
            
            iterations_left = max_iterations - iteration
            print(f"\n{'=' * 70}")
            print(f"📝 ITERATION {iteration}/{max_iterations} ({iterations_left} iterations remaining)")
            print(f"{'=' * 70}")
            
            trace.iteration_start(iteration, max_iterations)
            events.emit_iteration_start(iteration)  # Live monitoring
            
            # Phase 1: Generate Code
            print(f"\n🎨 Phase 1: Code Generation")
            print("-" * 70)
            
            gen_start_time = time.time()
            trace.generation_start(task)
            
            if iteration == 1:
                # First iteration: OpenHands processes todos one at a time
                print("🤖 OpenHands: Processing tasks from todo list...")
                
                # Copy template to workspace if it exists
                # Try multiple possible locations
                template_file = None
                possible_locations = [
                    base_dir.parent / "template.html",  # Match-me root
                    Path("/app/template.html"),  # Docker container
                    Path(__file__).parent.parent.parent / "template.html",  # Relative to this file
                ]
                
                for loc in possible_locations:
                    if loc.exists():
                        template_file = loc
                        break
                
                if template_file:
                    # Copy template to index.html in workspace (OpenHands will edit this file)
                    index_dest = state.workspace_dir / "index.html"
                    import shutil
                    import os
                    
                    # Read template and inject API key from environment variable
                    template_content = template_file.read_text(encoding='utf-8')
                    gemini_api_key = os.getenv('GOOGLE_AI_STUDIO_API_KEY', '')
                    
                    # Replace placeholder with actual API key (or empty if not set)
                    template_content = template_content.replace('{GEMINI_API_KEY}', gemini_api_key)
                    
                    # Write to destination
                    index_dest.write_text(template_content, encoding='utf-8')
                    
                    print(f"✅ Template loaded as index.html: {index_dest}")
                    print(f"   Source: {template_file}")
                    if gemini_api_key:
                        print(f"   ✅ Gemini API key injected from environment")
                    else:
                        print(f"   ⚠️  Warning: GOOGLE_AI_STUDIO_API_KEY not set - chatbot will be disabled")
                    print(f"   OpenHands will now process todos one at a time")
                else:
                    print("⚠️  Template file not found, OpenHands will create from scratch")
                    template_file = None
                
                # Get todo list from planner
                todo_list = plan.get('todo_list', [])
                if not todo_list:
                    # Fallback: use old approach if no todo list
                    print("⚠️  No todo list found, using full prompt approach")
                    generation_result = openhands.generate_code(
                        task=openhands_prompt,
                        workspace_path=str(state.workspace_dir),
                        detailed_requirements=None,
                        template_file=None
                    )
                    if not generation_result["success"]:
                        error_msg = generation_result.get("error", "Unknown error")
                        raise RuntimeError(f"❌ OpenHands code generation failed: {error_msg}")
                    files_generated = generation_result.get("files_generated", [])
                    diffs = generation_result.get("diffs", [])
                else:
                    # Process todos one at a time
                    print(f"📋 Processing {len(todo_list)} todo items...")
                    all_modules_info = plan.get('course_overview', {}).get('modules', [])
                    files_generated = []
                    diffs = []
                    
                    for todo_idx, todo in enumerate(todo_list):
                        print(f"\n{'='*70}")
                        print(f"📝 Todo {todo_idx + 1}/{len(todo_list)}: {todo['title']}")
                        print(f"{'='*70}")
                        
                        todo_result = openhands.execute_todo_task(
                            todo=todo,
                            workspace_path=str(state.workspace_dir),
                            all_modules_info=all_modules_info
                        )
                        
                        if not todo_result.get("success"):
                            error_msg = todo_result.get("error", "Unknown error")
                            print(f"⚠️  Todo '{todo['title']}' failed: {error_msg}")
                            # Continue with next todo instead of failing completely
                            continue
                        
                        # Collect files from this todo
                        todo_files = todo_result.get("files_generated", [])
                        files_generated.extend(todo_files)
                        print(f"✅ Todo completed: {todo_result.get('duration_seconds', 0):.2f}s")
                    
                    print(f"\n✅ All todos processed. Total files modified: {len(set(files_generated))}")
                    files_generated = list(set(files_generated))  # Remove duplicates
                
                print(f"✅ OpenHands generated: {', '.join(files_generated) if files_generated else 'No new files (edited existing)'}")
                if diffs:
                    print(f"📝 Diffs: {len(diffs)}")
                
                # Always check for index.html in workspace (even if not in files_generated)
                # This handles the case where OpenHands edited an existing file
                index_html = state.workspace_dir / "index.html"
                if index_html.exists() and "index.html" not in files_generated:
                    files_generated.append("index.html")
                    print(f"   Found index.html in workspace (edited by OpenHands)")
                
                # Copy to project_root for preview server
                import shutil
                for filename in files_generated:
                    workspace_file = state.workspace_dir / filename
                    if workspace_file.exists():
                        # Copy to site for compatibility
                        dest_file = state.site_dir / filename
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        # Use shutil.copy2 to handle both text and binary files
                        shutil.copy2(workspace_file, dest_file)
                        
                        # Copy to project_root for HTTP preview
                        project_file = path_config.project_root / filename
                        project_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(workspace_file, project_file)
                        print(f"   ✅ Copied {filename} to preview server directory")
                
                iter_result.files_generated = {f: str(state.workspace_dir / f) for f in files_generated}
                iter_result.code_generated = f"OpenHands: {','.join(files_generated)}"
                
                # Emit code generation event for live monitoring
                events.emit_code_generated(files_generated, method="openhands")
            else:
                print("🔄 Using patched files from previous iteration")
                files_generated = list(iter_result.files_generated.keys()) if iter_result.files_generated else ["index.html"]
            
            iter_result.generation_time_seconds = time.time() - gen_start_time
            print(f"   Time: {iter_result.generation_time_seconds:.2f}s")
            
            trace.generation_end(
                files_generated=files_generated if isinstance(files_generated, list) else [files_generated],
                duration=iter_result.generation_time_seconds
            )
            
            # Phase 2: Gemini-Controlled Browser QA
            print(f"\n🌐 Phase 2: Gemini-Controlled Browser QA")
            print("-" * 70)
            
            test_start_time = time.time()
            
            # Use HTTP preview URL (never file://)
            preview_url = preview_server.get_file_url("index.html")
            print(f"   Preview URL: {preview_url}")
            
            # Verify index.html exists in project_root (where preview server serves from)
            index_in_project = path_config.project_root / "index.html"
            if not index_in_project.exists():
                print(f"   ⚠️  WARNING: index.html not found in preview server directory!")
                print(f"   Expected: {index_in_project}")
                print(f"   Preview server serves from: {path_config.project_root}")
                # Check if it exists in workspace
                index_in_workspace = state.workspace_dir / "index.html"
                if index_in_workspace.exists():
                    print(f"   ✅ Found in workspace, copying to project_root...")
                    index_in_project.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(index_in_workspace, index_in_project)
                    print(f"   ✅ Copied to preview server directory")
                else:
                    print(f"   ❌ index.html not found in workspace either: {index_in_workspace}")
            else:
                print(f"   ✅ index.html found in preview server directory")
            
            trace.testing_start(preview_url)
            
            # Create screenshots directory for this iteration
            screenshots_dir = state.artifacts_dir / "screenshots" / f"iter_{iteration}"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"   Screenshots will be saved to: {screenshots_dir.name}/")
            
            iter_result.testing_time_seconds = time.time() - test_start_time
            
            trace.testing_end(
                screenshot_path=str(screenshots_dir),
                console_errors=0,  # Will be set by evaluator
                duration=iter_result.testing_time_seconds
            )
            
            # Phase 3: Comprehensive Evaluation
            print(f"\n🧠 Phase 3: Comprehensive Evaluation")
            print("-" * 70)
            
            eval_start_time = time.time()
            trace.evaluation_start(str(screenshots_dir))
            
            # Use new evaluator with interactive testing
            # Pass planner's detailed prompt to evaluator so it knows what to verify
            evaluation_task = task
            if iteration == 1 and 'openhands_prompt' in locals():
                # Include planner's detailed specifications in evaluation task
                evaluation_task = f"""{task}

**PLANNER SPECIFICATIONS (VERIFY THESE):**
{openhands_prompt}

**CRITICAL VERIFICATION REQUIREMENTS:**
- Verify the exact number of modules specified by the planner (check modules.length)
- Verify interactive activities match planner specifications (calculators/simulations, NOT quizzes if specified)
- Verify all modules from planner are present with correct titles and content
- If planner specified interactiveElement with calculators, verify calculators exist (NOT quizzes)
- If only 2 modules exist but planner specified 3, this is a CRITICAL FAILURE"""
            
            evaluation_result = await evaluator.evaluate(
                url=preview_url,
                mcp_client=mcp,
                task=evaluation_task,
                screenshots_dir=screenshots_dir
            )
            
            # Convert to dict for storage
            evaluation_dict = evaluator.to_dict(evaluation_result)
            
            # Save evaluation artifact
            eval_file = artifacts.save_evaluation(evaluation_dict, iteration)
            
            # Update iteration result
            iter_result.evaluation = evaluation_dict
            iter_result.score = evaluation_result.score
            iter_result.passed = evaluation_result.passed
            iter_result.feedback = evaluation_result.feedback
            iter_result.screenshot_path = evaluation_result.observations.desktop_screenshot
            iter_result.evaluation_time_seconds = time.time() - eval_start_time
            
            print(f"   Score: {iter_result.score}/100")
            print(f"   Status: {'✅ PASSED' if iter_result.passed else '❌ FAILED'}")
            print(f"   Time: {iter_result.evaluation_time_seconds:.2f}s")
            
            # Print category scores
            print(f"\n   Category Scores:")
            for category, score in evaluation_result.category_scores.items():
                max_score = {
                    "functionality": 25,
                    "ux": 25,
                    "accessibility": 20,
                    "responsiveness": 20,
                    "robustness": 10
                }.get(category, 100)
                percentage = (score / max_score * 100) if max_score > 0 else 0
                status = "✅" if percentage >= 70 else "❌"
                print(f"   {status} {category}: {score}/{max_score}")
            
            # Print key issues
            if evaluation_result.issues:
                print(f"\n   Key Issues ({len(evaluation_result.issues)}):")
                for i, issue in enumerate(evaluation_result.issues[:3], 1):
                    print(f"   {i}. [{issue.severity}] {issue.description[:60]}...")
            
            # Print fix suggestions
            if evaluation_result.fix_suggestions:
                print(f"\n   Fix Suggestions ({len(evaluation_result.fix_suggestions)}):")
                for i, suggestion in enumerate(evaluation_result.fix_suggestions[:3], 1):
                    print(f"   {i}. {suggestion[:60]}...")
            
            trace.evaluation_end(
                score=iter_result.score,
                passed=iter_result.passed,
                duration=iter_result.evaluation_time_seconds
            )
            
            # Calculate total iteration time
            iter_result.total_time_seconds = time.time() - iter_start_time
            
            # Add iteration to state
            state.result.add_iteration(iter_result)
            
            # Update manifest iteration count
            state.manifest.iteration_count = iteration
            state.manifest.final_score = iter_result.score
            state.manifest.final_passed = iter_result.passed
            
            trace.iteration_end(iteration, iter_result.score, iter_result.passed)
            
            # Emit evaluation event for live monitoring
            events.emit_evaluation(
                iteration=iteration,
                score=iter_result.score,
                passed=iter_result.passed,
                feedback=iter_result.feedback or ""
            )
            
            # Check if passed
            if iter_result.passed:
                print(f"\n🎉 SUCCESS! Evaluation passed on iteration {iteration}")
                state.result.complete("completed")
                state.manifest.complete("passed")
                break
            
            print(f"\n💬 Feedback: {iter_result.feedback[:200]}...")
            
            # If failed and not last iteration, try to fix with OpenHands
            if iteration < max_iterations and iter_result.score < 70:
                print(f"\n{'=' * 70}")
                print(f"🔧 Phase 4: OpenHands Patch Application")
                print(f"{'=' * 70}")
                
                patch_start_time = time.time()
                
                # Generate patch plan from evaluation
                print(f"\n📝 Generating patch plan from evaluation feedback...")
                patch_plan = generate_patch_plan(
                    evaluation=evaluation_dict,
                    task=task,
                    files_generated=iter_result.files_generated
                )
                
                # Add fix suggestions from evaluation
                if evaluation_result.fix_suggestions:
                    patch_plan["fix_suggestions_from_evaluator"] = evaluation_result.fix_suggestions
                
                # Save patch plan
                patch_plan_file = artifacts.save_file(
                    content=json.dumps(patch_plan, indent=2),
                    filename=f"patch_plan_iter_{iteration}.json",
                    file_type="patch_plan"
                )
                
                print(f"✅ Patch plan generated: {patch_plan_file.name}")
                print(f"   Files to patch: {len(patch_plan['files'])}")
                print(f"   Issues to fix: {patch_plan.get('issues_count', 0)}")
                
                trace.info(
                    "Patch plan generated",
                    data={
                        "iteration": iteration,
                        "files_count": len(patch_plan['files']),
                        "issues_count": patch_plan.get('issues_count', 0)
                    }
                )
                
                # Apply patch with OpenHands
                print(f"\n🔧 Applying patch via OpenHands...")
                
                try:
                    patch_result = openhands.apply_patch_plan(
                        workspace_path=str(state.workspace_dir),
                        patch_plan=patch_plan
                    )
                    
                    patch_duration = time.time() - patch_start_time
                    
                    # Log patch result
                    trace.info(
                        "Patch applied",
                        data={
                            "success": patch_result["success"],
                            "files_modified": patch_result["files_modified"],
                            "duration": patch_result["duration_seconds"]
                        }
                    )
                    
                    # Save patch result
                    artifacts.save_file(
                        content=json.dumps(patch_result, indent=2),
                        filename=f"patch_result_iter_{iteration}.json",
                        file_type="patch_result"
                    )
                    
                    if patch_result["success"]:
                        print(f"✅ Patch applied successfully")
                        print(f"   Files modified: {len(patch_result['files_modified'])}")
                        print(f"   Duration: {patch_duration:.2f}s")
                        
                        for file in patch_result["files_modified"]:
                            print(f"   - {file}")
                        
                        # Emit patch applied event for live monitoring
                        events.emit_patch_applied(patch_result["files_modified"])
                        
                        # Copy patched files to site and project_root
                        print(f"\n📋 Copying patched files...")
                        import shutil
                        for filename in patch_result["files_modified"]:
                            src = state.workspace_dir / filename
                            
                            # Copy to site (for compatibility)
                            dst_site = state.site_dir / filename
                            if src.exists():
                                dst_site.parent.mkdir(parents=True, exist_ok=True)
                                # Use shutil.copy2 to handle both text and binary files
                                shutil.copy2(src, dst_site)
                                
                                # Copy to project_root (for HTTP preview)
                                dst_project = path_config.safe_path_join(filename)
                                dst_project.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src, dst_project)
                                print(f"   ✅ Copied {filename} to preview server")
                        
                        # Commit and push to GitHub if enabled
                        if github.is_enabled():
                            print(f"\n🐙 Committing and pushing to GitHub...")
                            
                            commit_message = f"[Iteration {iteration}] Apply OpenHands patch (score: {iter_result.score}/100)"
                            run_branch = f"run/{config.run_id}"
                            
                            push_result = github.commit_and_push(
                                workspace_path=state.workspace_dir,
                                message=commit_message,
                                branch=run_branch
                            )
                            
                            if push_result["success"]:
                                if push_result.get("no_changes"):
                                    print(f"   ℹ️  No changes to commit")
                                else:
                                    print(f"   ✅ Pushed to {run_branch}")
                                    print(f"   Commit: {push_result['commit_sha'][:7]}")
                                    print(f"   URL: {push_result['commit_url']}")
                                    
                                    # Store commit info in trace and manifest
                                    trace.info("GitHub commit pushed", data=push_result)
                                    state.manifest.add_commit(
                                        iteration=iteration,
                                        commit_sha=push_result['commit_sha'],
                                        commit_url=push_result['commit_url']
                                    )
                            else:
                                print(f"   ⚠️  Push failed: {push_result['message']}")
                                trace.warning("GitHub push failed", data=push_result)
                        
                        print(f"\n🔄 Preparing re-evaluation (iteration {iteration + 1})...")
                    else:
                        print(f"❌ Patch application failed")
                        print(f"   Error: {patch_result.get('stderr', 'Unknown error')}")
                        
                        # Continue to next iteration anyway
                        if iteration < max_iterations:
                            print(f"\n🔄 Continuing to iteration {iteration + 1}...")
                
                except Exception as e:
                    logger.error(f"Error applying patch: {e}", exc_info=True)
                    print(f"❌ Error applying patch: {e}")
                    
                    trace.error(
                        message=f"Patch application failed: {e}",
                        error_type=type(e).__name__,
                        traceback=tb.format_exc()
                    )
            
            elif iteration < max_iterations:
                print(f"\n🔄 Preparing iteration {iteration + 1}...")
        
        # Mark as completed if we exhausted iterations
        if state.result.status == "running":
            state.result.complete("completed")
            state.manifest.complete("max_iterations")
        
        # Final results
        print(f"\n{'=' * 70}")
        print(f"🏁 FINAL RESULTS")
        print(f"{'=' * 70}")
        print(f"   Run ID: {config.run_id}")
        print(f"   Status: {state.result.status}")
        print(f"   Iterations: {state.result.current_iteration}")
        print(f"   Final score: {state.result.final_score}/100")
        print(f"   Status: {'✅ PASSED' if state.result.final_passed else '❌ FAILED'}")
        print(f"   Duration: {state.result.total_duration_seconds:.2f}s")
        print(f"   Preview: {state.result.preview_url}")
        
        # Print GitHub info if available
        if hasattr(state.result, 'github_branch_url') and state.result.github_branch_url:
            print(f"   🐙 GitHub: {state.result.github_branch_url}")
        
        # Save final report and manifest
        print(f"\n💾 Saving artifacts...")
        report_file = state.save_report()
        print(f"   Report: {report_file}")
        
        state_file = state.save_state()
        print(f"   State: {state_file}")
        
        manifest_file = state.save_manifest()
        print(f"   Manifest: {manifest_file}")
        
        # Create view.html
        view_html = create_view_html(state, artifacts)
        view_file = state.artifacts_dir / "view.html"
        view_file.write_text(view_html)
        print(f"   View: {view_file}")
        
        # Log artifacts summary
        artifacts_summary = artifacts.get_summary()
        trace.info("Artifacts saved", data=artifacts_summary)
        
        trace.run_end(
            run_id=config.run_id,
            status=state.result.status,
            result=state.result.to_dict()
        )
        
        print(f"\n✅ Run complete! View results at:")
        print(f"   {view_file}")
        
        # Emit run complete event for live monitoring
        events.emit_run_complete(
            run_id=config.run_id,
            final_score=state.result.final_score,
            passed=state.result.final_passed,
            iterations=state.result.current_iteration
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Error in orchestration loop: {e}", exc_info=True)
        
        # Log error to trace
        trace.error(
            message=str(e),
            error_type=type(e).__name__,
            traceback=tb.format_exc()
        )
        
        # Mark state as failed
        state.result.fail(str(e), tb.format_exc())
        state.manifest.complete("error")
        state.manifest.error_message = str(e)
        
        # Save state and manifest even on failure
        state.save_state()
        state.save_report()
        state.save_manifest()
        
        raise
        
    finally:
        # Cleanup
        if mcp:
            await mcp.disconnect()
        
        # Stop preview server
        print(f"\n🛑 Stopping preview server...")
        stop_preview_server()


def create_view_html(state: RunState, artifacts: ArtifactsManager) -> str:
    """Create view.html for displaying results"""
    
    # Get artifacts
    screenshots = artifacts.get_screenshots()
    evaluations = artifacts.get_evaluations()
    
    # Build screenshots HTML
    screenshots_html = ""
    for screenshot in screenshots:
        iter_num = screenshot['iteration']
        filename = screenshot['filename']
        eval_data = next((e for e in evaluations if e['iteration'] == iter_num), None)
        
        score = eval_data['score'] if eval_data else 0
        passed = eval_data['passed'] if eval_data else False
        
        screenshots_html += f"""
        <div class="iteration">
            <h3>Iteration {iter_num} - Score: {score}/100 {'✅' if passed else '❌'}</h3>
            <img src="{filename}" alt="Screenshot iteration {iter_num}">
        </div>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Run Results - {state.config.run_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f7fafc;
            padding: 40px 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            font-size: 28px;
            color: #1a202c;
            margin-bottom: 12px;
        }}
        
        .status {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 16px;
        }}
        
        .status.passed {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .status.failed {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}
        
        .meta-item {{
            padding: 12px;
            background: #f7fafc;
            border-radius: 6px;
        }}
        
        .meta-label {{
            font-size: 12px;
            color: #718096;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        
        .meta-value {{
            font-size: 16px;
            color: #1a202c;
            font-weight: 600;
        }}
        
        .task {{
            background: #edf2f7;
            padding: 16px;
            border-radius: 6px;
            margin-top: 16px;
            border-left: 4px solid #667eea;
        }}
        
        .iterations {{
            display: grid;
            gap: 24px;
        }}
        
        .iteration {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .iteration h3 {{
            font-size: 18px;
            color: #1a202c;
            margin-bottom: 16px;
        }}
        
        .iteration img {{
            width: 100%;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}
        
        .actions {{
            margin-top: 24px;
            display: flex;
            gap: 12px;
        }}
        
        .btn {{
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            display: inline-block;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-secondary {{
            background: #e2e8f0;
            color: #1a202c;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="status {'passed' if state.result.final_passed else 'failed'}">
                {state.result.status.upper()}
            </span>
            <h1>Run Results</h1>
            
            <div class="task">
                <strong>Task:</strong> {state.config.task}
            </div>
            
            <div class="meta">
                <div class="meta-item">
                    <div class="meta-label">Run ID</div>
                    <div class="meta-value">{state.config.run_id}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Final Score</div>
                    <div class="meta-value">{state.result.final_score}/100</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Iterations</div>
                    <div class="meta-value">{state.result.current_iteration}/{state.result.max_iterations}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Duration</div>
                    <div class="meta-value">{state.result.total_duration_seconds:.1f}s</div>
                </div>
            </div>
            
            <div class="actions">
                <a href="../../../preview/{state.config.run_id}/" class="btn btn-primary">View Preview</a>
                <a href="report.json" class="btn btn-secondary">View Report JSON</a>
                <a href="trace.jsonl" class="btn btn-secondary">View Trace</a>
            </div>
        </div>
        
        <div class="iterations">
            {screenshots_html}
        </div>
    </div>
    
    <script>
        // Auto-reload report data
        async function loadReport() {{
            try {{
                const response = await fetch('report.json');
                const report = await response.json();
                console.log('Report:', report);
            }} catch (error) {{
                console.error('Error loading report:', error);
            }}
        }}
        
        loadReport();
    </script>
</body>
</html>
"""
    
    return html


async def main():
    """Entry point"""
    
    # Default task for testing
    task = "Create a beautiful landing page for a SaaS product with hero section and CTA button"
    
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    
    try:
        state = await run_loop(task)
        return 0 if state.result.final_passed else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
