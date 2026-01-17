"""
Planner module using Gemini 3.0 Pro Preview to generate detailed prompts for OpenHands.
"""

import os
from pathlib import Path
import google.generativeai as genai
from typing import Dict, Any


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
    
    def generate_openhands_prompt(self, user_requirements: str, custom_notes: str = None) -> Dict[str, Any]:
        """
        Generate a detailed prompt for OpenHands based on user requirements.
        
        Args:
            user_requirements: The user's high-level description of what they want
            custom_notes: Optional custom notes/content to base the course on
        
        Returns:
            Dict containing:
                - prompt: The detailed prompt for OpenHands
                - thinking: Gemini's thinking process
                - metadata: Additional planning metadata
        """
        # Build input for planner
        if custom_notes:
            # Use custom notes as the primary content source
            planner_input = f"""CUSTOM NOTES/CONTENT PROVIDED:
{custom_notes}

TASK: {user_requirements}

Based on the custom notes/content above, generate a comprehensive, detailed prompt for OpenHands to create a single HTML file course page that covers all the topics and content from the notes. The prompt should instruct OpenHands to:
1. Create ONE single HTML file (index.html) with tabbed navigation
2. Organize the content from the notes into logical sections/tabs
3. Include all formulas, examples, and practice problems from the notes
4. Make it interactive and visually appealing
5. Ensure mathematical symbols render correctly (use KaTeX or MathJax)"""
        else:
            # Use standard task-based planning
            planner_input = f"""USER REQUIREMENTS:
{user_requirements}

Now generate a comprehensive, detailed prompt for OpenHands to implement this course. The prompt should be a clear set of instructions that OpenHands can follow to create the HTML files from scratch."""
        
        # Combine planner prompt with input
        full_prompt = f"""{self.planner_prompt}

{planner_input}"""
        
        print("🧠 Planner: Generating detailed prompt with Gemini 3.0 Pro Preview...")
        
        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 8192,
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
            generated_prompt = '\n'.join(response_parts)
            
            print(f"✅ Planner: Generated {len(generated_prompt)} character prompt")
            if thinking:
                print(f"💭 Planner: Thinking process captured ({len(thinking)} chars)")
            
            return {
                'prompt': generated_prompt,
                'thinking': thinking,
                'metadata': {
                    'model': 'gemini-3-pro-preview',
                    'user_requirements': user_requirements,
                    'used_custom_notes': custom_notes is not None,
                    'custom_notes_length': len(custom_notes) if custom_notes else 0,
                    'prompt_length': len(generated_prompt),
                    'has_thinking': thinking is not None
                }
            }
            
        except Exception as e:
            print(f"❌ Planner error: {e}")
            raise
    
    def save_plan(self, plan: Dict[str, Any], output_path: Path):
        """Save the generated plan to a file for inspection."""
        import json
        
        plan_file = output_path / 'planner_output.json'
        with open(plan_file, 'w') as f:
            json.dump(plan, f, indent=2)
        
        # Also save the prompt separately for easy reading
        prompt_file = output_path / 'openhands_prompt.txt'
        with open(prompt_file, 'w') as f:
            f.write(plan['prompt'])
        
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
