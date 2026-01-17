"""
Planner module using Gemini 3.0 Pro Preview to generate detailed prompts for OpenHands.
"""

import os
import json
import re
from pathlib import Path
import google.generativeai as genai
from typing import Dict, Any, List, Optional


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
    
    def _load_planner_prompt(self) -> str:
        """Load the planner prompt from file."""
        prompt_path = Path(__file__).parent / 'prompts' / 'planner_prompt.txt'
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Planner prompt not found at {prompt_path}")
        
        return prompt_path.read_text(encoding='utf-8')
    
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
        
        # Build the full prompt using the template format
        full_prompt = self.planner_prompt.format(
            user_requirements=user_requirements,
            notes=notes_text,
            youtube_links=youtube_links_text
        )
        
        print("🧠 Planner: Generating detailed prompt with Gemini 3.0 Pro Preview...")
        
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 8192,
                    'response_mime_type': 'application/json',  # Request JSON response
                }
            )
            
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
            
            # Parse JSON response
            try:
                # Try to extract JSON from response (might be wrapped in markdown)
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
                else:
                    # Try to find JSON object directly
                    json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                
                plan_json = json.loads(response_text)
                
                # Extract the OpenHands build prompt from the JSON
                generated_prompt = plan_json.get('openhands_build_prompt', response_text)
                
                # Store the full JSON structure
                course_overview = plan_json.get('course_overview', {})
                global_ui_spec = plan_json.get('global_ui_spec', {})
                
                print(f"✅ Planner: Generated JSON plan with {len(course_overview.get('modules', []))} modules")
                print(f"✅ Planner: Extracted {len(generated_prompt)} character OpenHands prompt")
                if thinking:
                    print(f"💭 Planner: Thinking process captured ({len(thinking)} chars)")
                
                return {
                    'prompt': generated_prompt,
                    'thinking': thinking,
                    'plan_json': plan_json,  # Full JSON structure
                    'course_overview': course_overview,
                    'global_ui_spec': global_ui_spec,
                    'metadata': {
                        'model': 'gemini-3-pro-preview',
                        'user_requirements': user_requirements,
                        'used_custom_notes': custom_notes is not None,
                        'custom_notes_length': len(custom_notes) if custom_notes else 0,
                        'prompt_length': len(generated_prompt),
                        'has_thinking': thinking is not None,
                        'youtube_videos_count': len(youtube_videos) if youtube_videos else 0,
                        'modules_count': len(course_overview.get('modules', []))
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
                        'model': 'gemini-3-pro-preview',
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
