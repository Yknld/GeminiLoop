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
            
            # Check for blocked/filtered responses
            if not response.candidates:
                print("⚠️  Response was blocked or filtered by safety settings")
                return []
            
            candidate = response.candidates[0]
            if candidate.finish_reason == 2:  # SAFETY
                print("⚠️  Response was blocked by safety filters")
                return []
            
            # Extract text from response - handle cases where text might not be available
            try:
                response_text = response.text.strip()
            except ValueError as e:
                # Response might not have text content
                print(f"⚠️  Could not extract text from response: {e}")
                print(f"   Finish reason: {candidate.finish_reason}")
                # Try to get content from parts
                if candidate.content and candidate.content.parts:
                    response_text = ''.join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                else:
                    return []
            
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
        Uses Gemini to understand the context and extract the main topic.
        
        Args:
            user_requirements: The user's high-level description
            custom_notes: Optional custom notes/content
            count: Number of videos to find
        
        Returns:
            List of video dictionaries
        """
        # Use Gemini to understand context and extract topic
        if custom_notes:
            print("📖 Analyzing notes with Gemini to understand context...")
            
            analysis_prompt = f"""Analyze the following educational notes and extract:
1. The main subject/topic (e.g., "geometry", "circles", "coordinate geometry")
2. Key concepts covered
3. Educational level (e.g., "high school", "undergraduate", "general")

NOTES:
{custom_notes[:3000]}

Return a JSON object with:
{{
  "main_topic": "clear topic name for YouTube search",
  "key_concepts": ["concept1", "concept2"],
  "educational_level": "level"
}}

Return ONLY the JSON, no other text."""
            
            try:
                analysis_response = self.model.generate_content(
                    analysis_prompt,
                    generation_config={
                        'temperature': 0.3,
                        'max_output_tokens': 512,
                    }
                )
                
                # Extract JSON from response
                analysis_text = analysis_response.text.strip()
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', analysis_text, re.DOTALL)
                if json_match:
                    analysis_text = json_match.group(1)
                else:
                    json_match = re.search(r'(\{.*?\})', analysis_text, re.DOTALL)
                    if json_match:
                        analysis_text = json_match.group(1)
                
                analysis = json.loads(analysis_text)
                topic = analysis.get('main_topic', user_requirements)
                key_concepts = analysis.get('key_concepts', [])
                
                print(f"✅ Extracted topic: {topic}")
                if key_concepts:
                    print(f"   Key concepts: {', '.join(key_concepts[:3])}")
                
                # Build context with key concepts
                context = f"Educational notes covering: {topic}"
                if key_concepts:
                    context += f". Key concepts: {', '.join(key_concepts[:5])}"
                context += f"\n\nNotes excerpt:\n{custom_notes[:1500]}"
                
            except Exception as e:
                print(f"⚠️  Error analyzing notes: {e}")
                print("   Falling back to simple topic extraction...")
                # Fallback to simple extraction
                topic = self._extract_topic_simple(custom_notes) or user_requirements
                context = custom_notes[:2000]
        else:
            topic = user_requirements
            context = None
        
        return self.find_videos(
            topic=topic,
            content_context=context,
            count=count
        )
    
    def _extract_topic_simple(self, notes: str) -> str:
        """Simple topic extraction fallback"""
        first_line = notes.split('\n')[0].strip()
        topic = re.sub(r'^#+\s*', '', first_line)
        topic = re.sub(r'\s*\([^)]*\)\s*', '', topic)
        topic = re.sub(r'^(Module Notes|Notes|Content|Topic):\s*', '', topic, flags=re.IGNORECASE)
        topic = ' '.join(topic.split())
        return topic if len(topic) > 3 else None


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
