"""
YouTube Video Finder

Uses YouTube Data API v3 to find real YouTube videos, with Gemini fallback.
Can be run beforehand to provide video options to the planner.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai

# Try to import YouTube API client
try:
    from googleapiclient.discovery import build
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False


class YouTubeFinder:
    """
    Finds relevant YouTube videos for educational content using Gemini 3 Pro Preview.
    """
    
    def __init__(self, api_key: str = None, youtube_api_key: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_AI_STUDIO_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
        
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 3 Pro Preview for finding videos (fallback)
        self.model = genai.GenerativeModel('gemini-2.0-pro-exp')
        
        # YouTube Data API v3 key (optional)
        self.youtube_api_key = youtube_api_key or os.getenv('YOUTUBE_API_KEY')
        self.use_youtube_api = YOUTUBE_API_AVAILABLE and self.youtube_api_key is not None
        
        if self.use_youtube_api:
            try:
                self.youtube_service = build('youtube', 'v3', developerKey=self.youtube_api_key)
                print("✅ YouTube Data API v3 initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize YouTube API: {e}")
                print("   Falling back to Gemini-based search")
                self.use_youtube_api = False
        else:
            if not YOUTUBE_API_AVAILABLE:
                print("⚠️  google-api-python-client not installed, using Gemini fallback")
            elif not self.youtube_api_key:
                print("⚠️  YOUTUBE_API_KEY not set, using Gemini fallback")
    
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
        
        # Use YouTube Data API if available, otherwise fallback to Gemini
        if self.use_youtube_api:
            return self._find_videos_with_api(topic, content_context, count, preferred_duration_min)
        else:
            return self._find_videos_with_gemini(topic, content_context, count, preferred_duration_min)
    
    def _find_videos_with_api(
        self,
        topic: str,
        content_context: str = None,
        count: int = 5,
        preferred_duration_min: tuple = (5, 20)
    ) -> List[Dict[str, Any]]:
        """Find videos using YouTube Data API v3"""
        print("📺 Using YouTube Data API v3...")
        
        try:
            # Build search query
            query = topic
            if content_context:
                # Add key terms from context
                context_words = content_context.split()[:10]  # First 10 words
                query = f"{topic} {' '.join(context_words)}"
            
            # Search for videos
            request = self.youtube_service.search().list(
                part='snippet',
                q=query,
                type='video',
                videoDuration='medium',  # 4-20 minutes (closest to preferred range)
                videoEmbeddable='true',  # Only embeddable videos
                order='relevance',  # Most relevant first
                maxResults=min(count * 2, 50)  # Get more to filter
            )
            
            response = request.execute()
            
            videos = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                
                # Get video details for duration
                try:
                    video_details = self.youtube_service.videos().list(
                        part='contentDetails',
                        id=video_id
                    ).execute()
                    
                    duration_str = video_details['items'][0]['contentDetails']['duration']
                    # Parse ISO 8601 duration (e.g., "PT5M30S" = 5 minutes 30 seconds)
                    duration_min = self._parse_duration(duration_str)
                    
                    # Filter by preferred duration if specified
                    if preferred_duration_min and not (preferred_duration_min[0] <= duration_min <= preferred_duration_min[1]):
                        continue
                except Exception as e:
                    print(f"   ⚠️  Could not get duration for video {video_id}: {e}")
                    duration_min = None
                
                video = {
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'title': snippet['title'],
                    'topic_section': topic,  # Can be refined with Gemini
                    'reason': f"Educational video about {topic}",
                    'channel': snippet['channelTitle'],
                    'published': snippet['publishedAt'],
                    'duration_min': duration_min
                }
                
                videos.append(video)
                
                if len(videos) >= count:
                    break
            
            print(f"✅ Found {len(videos)} videos via YouTube API")
            
            # Optionally use Gemini to refine relevance and add context
            if videos and content_context:
                videos = self._refine_videos_with_gemini(videos, topic, content_context)
            
            return videos
            
        except Exception as e:
            print(f"❌ Error using YouTube API: {e}")
            print("   Falling back to Gemini-based search...")
            return self._find_videos_with_gemini(topic, content_context, count, preferred_duration_min)
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse ISO 8601 duration to minutes"""
        import re
        # PT5M30S -> 5.5 minutes
        hours = re.search(r'(\d+)H', duration_str)
        minutes = re.search(r'(\d+)M', duration_str)
        seconds = re.search(r'(\d+)S', duration_str)
        
        total_minutes = 0.0
        if hours:
            total_minutes += float(hours.group(1)) * 60
        if minutes:
            total_minutes += float(minutes.group(1))
        if seconds:
            total_minutes += float(seconds.group(1)) / 60
        
        return total_minutes
    
    def _refine_videos_with_gemini(
        self,
        videos: List[Dict[str, Any]],
        topic: str,
        content_context: str
    ) -> List[Dict[str, Any]]:
        """Use Gemini to refine video relevance and add better context"""
        try:
            prompt = f"""Given these YouTube videos about {topic}, match them to specific aspects of the content:

CONTENT CONTEXT:
{content_context[:1500]}

VIDEOS:
{json.dumps([{'url': v['url'], 'title': v['title']} for v in videos], indent=2)}

For each video, provide:
- topic_section: Which specific aspect of {topic} this video covers
- reason: Why this video is relevant to the content

Return JSON array matching the video order:
[
  {{"topic_section": "...", "reason": "..."}},
  ...
]"""
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'response_mime_type': 'application/json',  # Request JSON directly
                }
            )
            
            # Check for safety blocks
            if not response.candidates:
                print("   ⚠️  Refinement response was blocked or filtered")
                return videos
            
            candidate = response.candidates[0]
            if candidate.finish_reason == 2:  # SAFETY
                print("   ⚠️  Refinement response blocked by safety filters")
                return videos
            
            # Extract text from response
            try:
                response_text = response.text.strip()
            except (ValueError, AttributeError):
                print("   ⚠️  Could not extract text from refinement response")
                return videos
            
            # Try to extract JSON if wrapped in markdown
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
                refinement = json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"   ⚠️  Could not parse refinement JSON: {e}")
                return videos
            
            # Apply refinements
            if isinstance(refinement, list):
                for i, video in enumerate(videos):
                    if i < len(refinement) and isinstance(refinement[i], dict):
                        video['topic_section'] = refinement[i].get('topic_section', topic)
                        video['reason'] = refinement[i].get('reason', video.get('reason', ''))
        except Exception as e:
            print(f"   ⚠️  Could not refine videos with Gemini: {e}")
        
        return videos
    
    def _find_videos_with_gemini(
        self,
        topic: str,
        content_context: str = None,
        count: int = 5,
        preferred_duration_min: tuple = (5, 20)
    ) -> List[Dict[str, Any]]:
        """Find videos using Gemini (fallback when API not available)"""
        print("🤖 Using Gemini to suggest videos (may not be real URLs)...")
        
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
            
            # Pass full notes to Gemini (not truncated)
            analysis_prompt = f"""Analyze the following educational notes and extract the main topics for YouTube video search.

NOTES:
{custom_notes}

Extract:
1. The main subject/topic(s) - this should be a clear, searchable topic name for YouTube (e.g., "geometry circles", "coordinate geometry", "geometry practice problems")
2. Key concepts covered
3. Educational level

Return a JSON object with:
{{
  "main_topic": "primary topic for YouTube search (can be multiple topics if notes cover different subjects)",
  "key_concepts": ["concept1", "concept2", "concept3"],
  "educational_level": "level"
}}

IMPORTANT: 
- The main_topic should be suitable for YouTube search queries
- If notes cover multiple distinct topics, list them (e.g., "circles, coordinate geometry, practice problems")
- Return ONLY valid JSON, no markdown, no explanation."""
            
            try:
                analysis_response = self.model.generate_content(
                    analysis_prompt,
                    generation_config={
                        'temperature': 0.3,
                        'max_output_tokens': 1024,
                        'response_mime_type': 'application/json',  # Request JSON directly
                    }
                )
                
                # Handle response - check for safety blocks
                if not analysis_response.candidates:
                    raise ValueError("Response blocked by safety filters")
                
                candidate = analysis_response.candidates[0]
                if candidate.finish_reason == 2:  # SAFETY
                    raise ValueError("Response blocked by safety filters (finish_reason: 2)")
                
                # Extract JSON from response
                try:
                    analysis_text = analysis_response.text.strip()
                except ValueError:
                    # Response might not have text, try to get from parts
                    if candidate.content and candidate.content.parts:
                        analysis_text = ''.join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                    else:
                        raise ValueError("No text content in response")
                
                # Try to extract JSON if wrapped in markdown
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', analysis_text, re.DOTALL)
                if json_match:
                    analysis_text = json_match.group(1)
                else:
                    # Try to find JSON object directly
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
                context += f"\n\nNotes excerpt:\n{custom_notes[:2000]}"
                
            except Exception as e:
                print(f"⚠️  Error analyzing notes with Gemini: {e}")
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
        if not notes:
            return None
        
        # Remove file path markers like "=== geometry_mock_notes/circles.md ==="
        notes = re.sub(r'^===.*?===\s*\n', '', notes, flags=re.MULTILINE)
        
        # Get first meaningful line (skip empty lines and file paths)
        lines = [line.strip() for line in notes.split('\n') if line.strip() and not line.strip().startswith('===')]
        if not lines:
            return None
        
        first_line = lines[0]
        
        # Remove markdown headers
        topic = re.sub(r'^#+\s*', '', first_line)
        
        # Remove parenthetical notes like "(Mock)"
        topic = re.sub(r'\s*\([^)]*\)\s*', '', topic)
        
        # Remove common prefixes
        topic = re.sub(r'^(Module Notes|Notes|Content|Topic|COORDINATE|Practice Problems):\s*', '', topic, flags=re.IGNORECASE)
        
        # Extract main topic from titles like "Module Notes — Circles" -> "Circles"
        if '—' in topic or '-' in topic:
            parts = re.split(r'[—\-]', topic)
            if len(parts) > 1:
                topic = parts[-1].strip()
        
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
