"""
Planner module using Gemini 3.0 Pro Preview to generate detailed prompts for OpenHands.
"""

import os
import json
import re
import time
from pathlib import Path
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from typing import Dict, Any, List, Optional, Tuple


class Planner:
    """
    Uses Gemini 3.0 Pro Preview to analyze requirements and generate
    a detailed, descriptive prompt for OpenHands to create HTML from scratch.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_AI_STUDIO_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
        
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 3.0 Pro Preview for planning
        self.model = genai.GenerativeModel('gemini-3-pro-preview')
        
        # Load planner prompt
        self.planner_prompt = self._load_planner_prompt()
        
        # Load template summary if available
        # Try multiple possible locations (in order of preference)
        possible_paths = [
            Path("/app/TEMPLATE_SUMMARY.md"),  # Docker container root (primary location)
            Path(__file__).parent.parent / "TEMPLATE_SUMMARY.md",  # GeminiLoop root (if running locally)
            Path(__file__).parent.parent.parent / "TEMPLATE_SUMMARY.md",  # Match-me root (if running from parent)
            Path.cwd() / "TEMPLATE_SUMMARY.md",  # Current working directory
        ]
        
        template_summary_file = None
        for path in possible_paths:
            if path.exists():
                template_summary_file = path
                break
        
        if template_summary_file:
            try:
                self.template_summary = template_summary_file.read_text(encoding='utf-8')
                print(f"✅ Template summary loaded from: {template_summary_file}")
            except Exception as e:
                print(f"⚠️  Failed to read template summary from {template_summary_file}: {e}")
                self.template_summary = None
        else:
            self.template_summary = None
            print("⚠️  Template summary not found, proceeding without template context")
            print(f"   Searched paths: {[str(p) for p in possible_paths]}")
    
    def _load_planner_prompt(self) -> str:
        """Load the planner prompt from file."""
        prompt_path = Path(__file__).parent / 'prompts' / 'planner_prompt.txt'
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Planner prompt not found at {prompt_path}")
        
        return prompt_path.read_text(encoding='utf-8')
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        Robustly extract JSON from text that may contain markdown, extra text, etc.
        Uses recursive brace matching instead of fragile regex.
        """
        # First, try to find JSON in markdown code blocks
        markdown_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
        ]
        
        for pattern in markdown_patterns:
            matches = list(re.finditer(pattern, text, re.DOTALL))
            if matches:
                # Try each match, return first valid JSON
                for match in matches:
                    candidate = match.group(1).strip()
                    if self._is_valid_json(candidate):
                        return candidate
        
        # If no markdown block found, find JSON object by matching braces
        # Find all potential JSON object starts
        start_positions = []
        for i, char in enumerate(text):
            if char == '{':
                start_positions.append(i)
        
        # Try each potential start position
        for start_pos in start_positions:
            # Find matching closing brace
            brace_count = 0
            end_pos = None
            
            for i in range(start_pos, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            
            if end_pos:
                candidate = text[start_pos:end_pos].strip()
                if self._is_valid_json(candidate):
                    return candidate
        
        return None
    
    def _is_valid_json(self, text: str) -> bool:
        """Check if text is valid JSON."""
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            return False
    
    def generate_openhands_prompt(
        self, 
        user_requirements: str, 
        custom_notes: str = None,
        youtube_videos: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed prompt for OpenHands based on user requirements.
        
        Args:
            user_requirements: The user's high-level description of what they want
            custom_notes: Optional custom notes/content to base the course on
            youtube_videos: Optional list of YouTube videos to embed. Each dict should have:
                - url: YouTube URL
                - title: Video title (optional)
                - topic_section: Which topic this covers (optional)
                - reason: Why this video is relevant (optional)
        
        Returns:
            Dict containing:
                - prompt: The detailed prompt for OpenHands
                - thinking: Gemini's thinking process
                - metadata: Additional planning metadata
        """
        # Format YouTube links for the prompt template
        youtube_links_text = "None provided"
        if youtube_videos and len(youtube_videos) > 0:
            links_list = []
            for video in youtube_videos:
                url = video.get('url', '')
                if url:
                    link_info = url
                    title = video.get('title', '')
                    if title:
                        link_info += f" (Title: {title})"
                    links_list.append(link_info)
            youtube_links_text = '\n'.join(links_list)
        
        # Format notes - use custom_notes if provided, otherwise use user_requirements
        notes_text = custom_notes if custom_notes else user_requirements
        
        # Get TTS API key from environment (use GOOGLE_TTS_API_KEY if available, fallback to GOOGLE_AI_STUDIO_API_KEY)
        tts_api_key = os.getenv('GOOGLE_TTS_API_KEY') or os.getenv('GOOGLE_AI_STUDIO_API_KEY') or 'NOT_SET'
        if tts_api_key == 'NOT_SET':
            print("⚠️  Warning: TTS API key not set. Audio generation may fail.")
        
        # Add template summary to prompt if available
        template_context = ""
        if self.template_summary:
            template_context = f"\n\nTEMPLATE SUMMARY (for reference):\n{self.template_summary}\n"
        
        # Build the full prompt using safe template replacement
        # Use a unique delimiter approach to avoid conflicts if placeholders appear in content
        # Replace in reverse order of likelihood to contain other placeholders
        full_prompt = self.planner_prompt
        
        # Use a safer replacement method that handles edge cases
        # Replace placeholders one at a time, checking for conflicts
        replacements = {
            "{tts_api_key}": tts_api_key,
            "{user_requirements}": user_requirements,
            "{notes}": notes_text,
            "{youtube_links}": youtube_links_text,
        }
        
        # Replace in order, but validate no placeholder appears in replacement values
        for placeholder, value in replacements.items():
            # Check if this placeholder appears in any replacement value (would cause double replacement)
            if any(placeholder in str(v) for k, v in replacements.items() if k != placeholder):
                print(f"⚠️  Warning: Placeholder {placeholder} found in replacement value - may cause issues")
            
            # Perform replacement
            if placeholder in full_prompt:
                full_prompt = full_prompt.replace(placeholder, str(value))
        
        # Append template summary if available
        if template_context:
            full_prompt += template_context
        
        print("🧠 Planner: Generating detailed prompt with Gemini 3.0 Pro Preview...")
        print("   ⚠️  Reminder: Planner must output natural language only, NO code")
        
        # Add explicit instruction to avoid code generation
        system_instruction = "CRITICAL: You are a PLANNER, not a CODER. Your output must be 100% natural language text - no HTML, no JavaScript, no code snippets. Describe what should be built using plain English, not programming languages."
        
        # Retry logic for quota errors
        max_retries = 5
        retry_delay = 15  # Default delay in seconds
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    f"{system_instruction}\n\n{full_prompt}",
                    generation_config={
                        'temperature': 0.7,
                        'top_p': 0.95,
                        'top_k': 40,
                        'max_output_tokens': 8192,
                        'response_mime_type': 'application/json',  # Request JSON response
                    }
                )
                break  # Success, exit retry loop
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a quota/resource exhausted error
                if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    # Try to extract retry delay from error message
                    retry_match = re.search(r'retry.*?(\d+\.?\d*)\s*s', error_str, re.IGNORECASE)
                    if retry_match:
                        retry_delay = float(retry_match.group(1)) + 2  # Add 2s buffer
                    else:
                        # Exponential backoff: 15s, 30s, 60s, 120s
                        retry_delay = 15 * (2 ** attempt)
                    
                    if attempt < max_retries - 1:
                        print(f"⚠️  Quota exceeded (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay:.1f}s...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"❌ Quota exceeded after {max_retries} attempts")
                        raise
                else:
                    # Not a quota error, re-raise immediately
                    raise
        
        # Extract thinking and response
        thinking_parts = []
        response_parts = []
        
        for part in response.parts:
            if hasattr(part, 'thought') and part.thought:
                thinking_parts.append(part.text)
            else:
                response_parts.append(part.text)
        
        thinking = '\n'.join(thinking_parts) if thinking_parts else None
        response_text = '\n'.join(response_parts)
        
        # Parse JSON response using robust extraction
        try:
            # Use robust JSON extraction
            extracted_json = self._extract_json_from_text(response_text)
            
            if not extracted_json:
                raise ValueError("Could not extract valid JSON from response")
            
            plan_json = json.loads(extracted_json)
            
            # Extract the OpenHands build prompt from the JSON
            generated_prompt = plan_json.get('openhands_build_prompt', response_text)
            
            # Store the full JSON structure
            course_overview = plan_json.get('course_overview', {})
            global_ui_spec = plan_json.get('global_ui_spec', {})
            
            print(f"✅ Planner: Generated JSON plan with {len(course_overview.get('modules', []))} modules")
            print(f"✅ Planner: Extracted {len(generated_prompt)} character OpenHands prompt")
            if thinking:
                print(f"💭 Planner: Thinking process captured ({len(thinking)} chars)")
            
            # Generate todo list from modules
            todo_list = self._generate_todo_list(course_overview, plan_json)
            
            return {
                'prompt': generated_prompt,
                'thinking': thinking,
                'plan_json': plan_json,  # Full JSON structure
                'course_overview': course_overview,
                'global_ui_spec': global_ui_spec,
                'todo_list': todo_list,  # Structured todo list for step-by-step execution
                'metadata': {
                    'model': 'gemini-1.5-flash',
                    'user_requirements': user_requirements,
                    'used_custom_notes': custom_notes is not None,
                    'custom_notes_length': len(custom_notes) if custom_notes else 0,
                    'prompt_length': len(generated_prompt),
                    'has_thinking': thinking is not None,
                    'youtube_videos_count': len(youtube_videos) if youtube_videos else 0,
                    'modules_count': len(course_overview.get('modules', [])),
                    'todo_count': len(todo_list)
                }
            }
        except (json.JSONDecodeError, KeyError) as e:
                # Fallback: if JSON parsing fails, use the raw response as prompt
                print(f"⚠️  Warning: Failed to parse JSON response, using raw response: {e}")
                print(f"   Response preview: {response_text[:200]}...")
                
                return {
                    'prompt': response_text,
                    'thinking': thinking,
                    'metadata': {
                        'model': 'gemini-2.0-pro-exp',
                        'user_requirements': user_requirements,
                        'used_custom_notes': custom_notes is not None,
                        'custom_notes_length': len(custom_notes) if custom_notes else 0,
                        'prompt_length': len(response_text),
                        'has_thinking': thinking is not None,
                        'youtube_videos_count': len(youtube_videos) if youtube_videos else 0,
                        'json_parse_error': str(e)
                    }
                }
            
        except Exception as e:
            print(f"❌ Planner error: {e}")
            raise
    
    def _generate_todo_list(self, course_overview: Dict[str, Any], plan_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate a structured todo list from the course overview.
        Each todo item represents one module to be created.
        """
        todos = []
        modules = course_overview.get('modules', [])
        
        # Extract module specifications from openhands_build_prompt if available
        openhands_prompt = plan_json.get('openhands_build_prompt', '')
        
        # Initial setup todo
        todos.append({
            'id': 'setup',
            'type': 'setup',
            'title': 'Initialize template and understand structure',
            'description': 'Read index.html, understand template structure (modules array, navigation, etc.)',
            'module_index': None,
            'priority': 1
        })
        
        # One todo per module
        for idx, module in enumerate(modules):
            module_id = module.get('module_id', f'm{idx+1}')
            module_title = module.get('module_title', f'Module {idx+1}')
            
            # Extract module-specific details from the prompt if available
            # Look for "MODULE X:" sections in the prompt
            module_spec = self._extract_module_spec_from_prompt(openhands_prompt, idx + 1, module_title)
            
            todos.append({
                'id': f'module_{idx}',
                'type': 'module',
                'title': f'Create Module {idx+1}: {module_title}',
                'description': f'Add Module {idx+1} ({module_title}) to the modules array with all required fields',
                'module_index': idx,
                'module_id': module_id,
                'module_title': module_title,
                'module_spec': module_spec,  # Detailed specifications from prompt
                'module_data': {
                    'title': module_title,
                    'videoId': module_spec.get('videoId'),
                    'explanation': module_spec.get('explanation'),
                    'keyPoints': module_spec.get('keyPoints', []),
                    'timeline': module_spec.get('timeline', []),
                    'funFact': module_spec.get('funFact'),
                    'interactiveElement': None,  # Will be generated
                    'audioSources': {}
                },
                'requirements': {
                    'explanation': module_spec.get('explanation_desc', 'Main explanation text from notes'),
                    'keyPoints': module_spec.get('keyPoints_desc', 'Important concepts as array'),
                    'timeline': module_spec.get('timeline_desc', 'Historical events/chronology (if applicable)'),
                    'funFact': module_spec.get('funFact_desc', 'Interesting fact'),
                    'interactiveElement': 'FUN interactive activity (calculator/simulation/game - NEVER quiz/test)',
                    'videoId': module_spec.get('videoId_desc', 'YouTube video ID (from provided videos)')
                },
                'interactive_experiences': module.get('interactive_experiences', []),
                'priority': idx + 2  # After setup
            })
        
        # Final validation todo
        todos.append({
            'id': 'validation',
            'type': 'validation',
            'title': 'Final validation and cleanup',
            'description': 'Verify all modules are created, interactive elements work, no placeholders remain',
            'module_index': None,
            'priority': len(modules) + 2
        })
        
        return todos
    
    def _extract_module_spec_from_prompt(self, prompt: str, module_num: int, module_title: str) -> Dict[str, Any]:
        """Extract module-specific specifications from the openhands_build_prompt"""
        spec = {}
        
        # Look for "MODULE X:" or module title in prompt
        import re
        next_module_num = module_num + 1
        module_pattern = rf'\*\*MODULE\s+{module_num}[:\*]?\*\*.*?(?=\*\*MODULE\s+{next_module_num}|\*\*MODULE\s+\d+|\*\*AUDIO|\*\*FINAL|$)'
        match = re.search(module_pattern, prompt, re.IGNORECASE | re.DOTALL)
        
        if match:
            module_text = match.group(0)
            
            # Extract videoId
            video_match = re.search(r'videoId[:\s]*["\']?([^"\'\s]+)["\']?', module_text, re.IGNORECASE)
            if video_match:
                spec['videoId'] = video_match.group(1)
                spec['videoId_desc'] = f'Use video ID: {spec["videoId"]}'
            
            # Extract explanation
            exp_match = re.search(r'explanation[:\s]*([^\n]+)', module_text, re.IGNORECASE)
            if exp_match:
                spec['explanation'] = exp_match.group(1).strip()
                spec['explanation_desc'] = spec['explanation']
            
            # Extract interactiveElement description
            interactive_match = re.search(r'interactiveElement[:\s]*\*\*.*?\*\*[:\s]*(.*?)(?=\*\*|$)', module_text, re.IGNORECASE | re.DOTALL)
            if interactive_match:
                spec['interactiveElement_desc'] = interactive_match.group(1).strip()
        
        return spec
    
    def save_plan(self, plan: Dict[str, Any], output_path: Path):
        """Save the generated plan to a file for inspection."""
        plan_file = output_path / 'planner_output.json'
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2)
        
        # Also save the prompt separately for easy reading
        prompt_file = output_path / 'openhands_prompt.txt'
        with open(prompt_file, 'w') as f:
            f.write(plan['prompt'])
        
        # Save the full JSON plan structure if available
        if plan.get('plan_json'):
            plan_json_file = output_path / 'course_plan.json'
            with open(plan_json_file, 'w') as f:
                json.dump(plan['plan_json'], f, indent=2)
        
        # Save todo list if available
        if plan.get('todo_list'):
            todo_file = output_path / 'todo_list.json'
            with open(todo_file, 'w') as f:
                json.dump(plan['todo_list'], f, indent=2)
            print(f"   Todo list: {todo_file} ({len(plan['todo_list'])} items)")
        
        if plan.get('thinking'):
            thinking_file = output_path / 'planner_thinking.txt'
            with open(thinking_file, 'w') as f:
                f.write(plan['thinking'])
        
        print(f"💾 Plan saved to {output_path}")


def main():
    """Test the planner."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.planner 'Create a quiz app about geography'")
        sys.exit(1)
    
    user_req = ' '.join(sys.argv[1:])
    
    planner = Planner()
    plan = planner.generate_openhands_prompt(user_req)
    
    print("\n" + "="*80)
    print("GENERATED OPENHANDS PROMPT:")
    print("="*80)
    print(plan['prompt'])
    print("="*80)
    
    if plan.get('thinking'):
        print("\nTHINKING PROCESS:")
        print("="*80)
        print(plan['thinking'])
        print("="*80)


if __name__ == '__main__':
    main()
