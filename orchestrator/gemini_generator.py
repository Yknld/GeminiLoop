"""
Gemini Code Generator

Uses Gemini 2.0 Flash directly for code generation
No IDE dependencies - pure Gemini API
"""

import os
from typing import Dict, Any
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    raise ImportError("Install google-generativeai: pip install google-generativeai")


class GeminiCodeGenerator:
    """
    Direct Gemini code generator for RunPod deployment
    
    Serverless-friendly approach:
    - No IDE dependencies
    - Pure Gemini API
    - Fast and scalable
    """
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        # Use Gemini 2.0 Flash (latest available model)
        self.model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": 8000,
            }
        )
    
    async def generate(self, task: str, workspace_dir: Path) -> Dict[str, Any]:
        """
        Generate code using Gemini
        
        Args:
            task: Natural language description
            workspace_dir: Directory to save generated code
        
        Returns:
            {
                "code": str,
                "file_path": str,
                "filename": str
            }
        """
        
        prompt = self._build_generation_prompt(task)
        
        # Call Gemini for code generation
        response = self.model.generate_content(prompt)
        
        # Parse response
        result = self._parse_generation(response.text, task)
        
        # Write to workspace
        output_file = workspace_dir / result["filename"]
        output_file.write_text(result["code"])
        
        result["file_path"] = str(output_file)
        
        return result
    
    def _build_generation_prompt(self, task: str) -> str:
        """Build code generation prompt"""
        
        prompt = f"""You are an expert full-stack developer.

**TASK:**
{task}

**YOUR OBJECTIVE:**
Generate production-ready code that:
1. Fulfills the task requirements completely
2. Uses clean, modern design
3. Follows best practices
4. Is fully functional
5. Has excellent UX/UI

**DESIGN PRINCIPLES:**
- Clean, minimalist aesthetic
- Smooth animations and interactions
- Excellent spacing and typography
- Responsive design
- Professional color palette
- No external dependencies (self-contained HTML/CSS/JS)

**OUTPUT FORMAT:**
Return ONLY the HTML code in this format:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Page</title>
    <style>
        /* Your CSS here */
    </style>
</head>
<body>
    <!-- Your HTML here -->
    
    <script>
        // Your JavaScript here
    </script>
</body>
</html>
```

**IMPORTANT:**
- Return ONLY the HTML code
- No explanations
- Complete, working solution
- Production-ready quality

Generate now:
"""
        
        return prompt
    
    def _parse_generation(self, response_text: str, task: str) -> Dict[str, Any]:
        """Parse Gemini's code generation response"""
        
        # Extract code from markdown blocks if present
        code = response_text.strip()
        
        if "```html" in code:
            start = code.find("```html") + 7
            end = code.find("```", start)
            code = code[start:end].strip()
        elif "```" in code:
            start = code.find("```") + 3
            end = code.find("```", start)
            code = code[start:end].strip()
        
        # If code doesn't start with <!DOCTYPE>, try to find HTML
        if not code.startswith("<!DOCTYPE") and not code.startswith("<html"):
            if "<!DOCTYPE" in response_text:
                start = response_text.find("<!DOCTYPE")
                code = response_text[start:]
                if "</html>" in code:
                    end = code.find("</html>") + 7
                    code = code[:end]
        
        return {
            "code": code,
            "filename": "index.html",
            "language": "html"
        }
