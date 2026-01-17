"""
YouTube Video Finder

Uses Gemini 3 Pro Preview to find relevant YouTube videos for course topics.
Can be run beforehand to provide video options to the planner.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai


class YouTubeFinder:
    """
    Finds relevant YouTube videos for educational content using Gemini 3 Pro Preview.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_AI_STUDIO_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
        
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 3 Pro Preview for finding videos
        self.model = genai.GenerativeModel('gemini-3-pro-preview')
    
    def find_videos(
        self, 
        topic: str, 
        content_context: str = None,
        count: int = 5,
        preferred_duration_min: tuple = (5, 20)
    ) -> List[Dict[str, Any]]:
        """
        Find YouTube videos relevant to a topic.
        
        Args:
            topic: The main topic or subject (e.g., "geometry of shapes")
            content_context: Optional additional context about the content
            count: Number of videos to find (default 5)
            preferred_duration_min: Preferred duration range in minutes (min, max)
        
        Returns:
            List of video dictionaries with:
                - url: YouTube URL
                - title: Video title (if available)
                - topic_section: Which part of the topic this video covers
                - reason: Why this video is relevant
        """
        # Build prompt for Gemini
        context_part = ""
        if content_context:
            context_part = f"""
CONTENT CONTEXT:
{content_context[:2000]}  # Limit context to avoid token limits
"""
        
        prompt = f"""Find {count} relevant YouTube explainer videos for the following educational topic.

TOPIC: {topic}
{context_part}
Please find YouTube videos that are:
- Clear, educational explainer videos
- Relevant to the topic
- Ideally {preferred_duration_min[0]}-{preferred_duration_min[1]} minutes long (but any length is acceptable)
- From educational channels when possible

For each video, provide:
1. The full YouTube URL (https://www.youtube.com/watch?v=...)
2. The video title (if you can determine it)
3. Which specific aspect of the topic this video covers
4. A brief reason why this video is relevant

Return the results as a JSON array with this structure:
[
  {{
    "url": "https://www.youtube.com/watch?v=...",
    "title": "Video title here",
    "topic_section": "Specific aspect this covers",
    "reason": "Why this video is relevant"
  }},
  ...
]

Return ONLY the JSON array, no other text."""

        print(f"🔍 Finding YouTube videos for: {topic}")
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                }
            )
            
            # Extract text from response
            response_text = response.text.strip()
            
            # Try to extract JSON from the response
            # Sometimes Gemini wraps JSON in markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'(\[.*?\])', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            # Parse JSON
            try:
                videos = json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract URLs manually
                print("⚠️  JSON parsing failed, extracting URLs manually...")
                videos = self._extract_videos_from_text(response_text)
            
            # Validate and clean up videos
            validated_videos = []
            for video in videos:
                if isinstance(video, dict) and 'url' in video:
                    # Ensure URL is valid YouTube URL
                    url = video['url']
                    if 'youtube.com/watch' in url or 'youtu.be' in url:
                        validated_videos.append({
                            'url': url,
                            'title': video.get('title', ''),
                            'topic_section': video.get('topic_section', ''),
                            'reason': video.get('reason', 'Relevant to topic')
                        })
            
            print(f"✅ Found {len(validated_videos)} YouTube videos")
            return validated_videos[:count]  # Limit to requested count
            
        except Exception as e:
            print(f"❌ Error finding videos: {e}")
            # Return empty list on error
            return []
    
    def _extract_videos_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Fallback: Extract YouTube URLs from text if JSON parsing fails."""
        videos = []
        
        # Find all YouTube URLs
        url_pattern = r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)'
        matches = re.finditer(url_pattern, text)
        
        for match in matches:
            video_id = match.group(1)
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Try to extract context around the URL
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]
            
            videos.append({
                'url': url,
                'title': '',
                'topic_section': '',
                'reason': 'Found in response'
            })
        
        return videos
    
    def find_videos_for_content(
        self,
        user_requirements: str,
        custom_notes: str = None,
        count: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find YouTube videos based on user requirements and optional custom notes.
        This is the main entry point for the planner integration.
        
        Args:
            user_requirements: The user's high-level description
            custom_notes: Optional custom notes/content
            count: Number of videos to find
        
        Returns:
            List of video dictionaries
        """
        # Determine the main topic from requirements or notes
        if custom_notes:
            # Extract topic from custom notes - clean up markdown and parenthetical notes
            first_line = custom_notes.split('\n')[0].strip()
            
            # Remove markdown headers (# ## ###)
            topic = re.sub(r'^#+\s*', '', first_line)
            
            # Remove parenthetical notes like "(Mock)", "(Optional)", etc.
            topic = re.sub(r'\s*\([^)]*\)\s*', '', topic)
            
            # Remove common prefixes
            topic = re.sub(r'^(Module Notes|Notes|Content|Topic):\s*', '', topic, flags=re.IGNORECASE)
            
            # Clean up extra whitespace
            topic = ' '.join(topic.split())
            
            # If topic is still too generic or empty, use a better extraction
            if not topic or len(topic) < 3:
                # Try to find a better topic from the content
                lines = custom_notes.split('\n')[:10]  # Check first 10 lines
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and len(line) > 10:
                        # Remove markdown and parentheticals
                        clean_line = re.sub(r'^#+\s*', '', line)
                        clean_line = re.sub(r'\s*\([^)]*\)\s*', '', clean_line)
                        clean_line = re.sub(r'^(Module Notes|Notes|Content|Topic):\s*', '', clean_line, flags=re.IGNORECASE)
                        clean_line = ' '.join(clean_line.split())
                        if clean_line and len(clean_line) > 10:
                            topic = clean_line[:200]
                            break
            
            # Fallback to user_requirements if topic extraction failed
            if not topic or len(topic) < 3:
                topic = user_requirements
            
            context = custom_notes[:2000]  # Use first 2000 chars as context
        else:
            topic = user_requirements
            context = None
        
        return self.find_videos(
            topic=topic,
            content_context=context,
            count=count
        )


def main():
    """Test the YouTube finder."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m orchestrator.youtube_finder 'geometry of shapes'")
        sys.exit(1)
    
    topic = ' '.join(sys.argv[1:])
    
    finder = YouTubeFinder()
    videos = finder.find_videos(topic, count=5)
    
    print("\n" + "="*80)
    print("FOUND YOUTUBE VIDEOS:")
    print("="*80)
    for i, video in enumerate(videos, 1):
        print(f"\n{i}. {video.get('title', 'No title')}")
        print(f"   URL: {video['url']}")
        print(f"   Section: {video.get('topic_section', 'N/A')}")
        print(f"   Reason: {video.get('reason', 'N/A')}")
    print("="*80)


if __name__ == '__main__':
    main()
