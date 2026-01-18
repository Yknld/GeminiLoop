# Interactive Notes Template - Module Structure & Flow

## Overview
A single-page HTML application that generates interactive, multimedia learning modules. Each module is a self-contained lesson with video, text, timeline, activities, and AI-powered assistance.

## Module Structure

### Core Properties
Each module object contains:

```javascript
{
  title: "Module Title",
  videoId: "YouTube video ID",
  explanation: "Main explanatory text content",
  keyPoints: [
    { text: "Key point text", audioId: "keypoint-0" }
  ],
  timeline: [
    {
      date: "1800",
      title: "Event Title",
      description: "Event description",
      person: "Key Person Name",
      audioId: "timeline-0"
    }
  ],
  funFact: "Interesting fact text",
  interactiveElement: "HTML content for interactive activities",
  audioSources: {
    "explanation": "audio-url.mp3",
    "video": "audio-url.mp3",
    "timeline-section": "audio-url.mp3",
    "interactive": "audio-url.mp3",
    "funfact": "audio-url.mp3",
    "keypoint-0": "audio-url.mp3",
    "timeline-0": "audio-url.mp3"
  }
}
```

## Template Components

### 1. Navigation Bar (Top)
- **Module Selector**: Dropdown to jump between modules
- **Previous/Next Buttons**: Sequential navigation
- **Progress Indicator**: "X of Y" module counter
- **State Persistence**: Current module saved to localStorage

### 2. Main Content Area

#### Video Section
- YouTube embed (responsive, reduced size)
- Audio playback control (microphone icon)
- Supports YouTube video IDs

#### Explanation Section
- Main explanatory text
- Audio playback control
- Large, readable text area

#### Key Points Section
- Bulleted list of important concepts
- Individual audio controls per point
- Styled as cards with hover effects

#### Timeline Section
- Vertical timeline with events
- Each event shows: date, title, description, person
- Section-level audio control (entire timeline)
- Individual audio controls per event
- Visual timeline connector line

#### Interactive Activity Section
- Flexible container for quizzes, exercises, games
- Supports HTML content injection
- Audio playback control

### 3. Right Sidebar

#### Fun Fact Card
- Highlighted sidebar element
- Audio playback control
- Styled with gradient accent

### 4. Floating Action Buttons (Bottom Right)

#### Notes Button
- Floating circular button (64px)
- Opens expandable panel
- Textarea for user notes
- Auto-saves per module to localStorage
- Module-specific storage keys

#### Chatbot Button
- Floating circular button (64px)
- Gemini 2.0 Flash API integration
- Conversation history maintained
- "Ask Gemini" feature: highlight text → button appears → populates chat input
- Direct API calls (no backend required)

## Interactive Features

### Audio Playback System
- **Universal Controls**: Microphone icons on all content sections
- **Auto-stop**: Playing new audio stops currently playing audio
- **Per-section Audio**: Each section can have its own TTS audio file
- **Dynamic Loading**: Audio sources set via `audioSources` object

### Text Selection & AI Integration
- **"Ask Gemini" Feature**: 
  - User highlights any text
  - Floating button appears near selection
  - Clicking adds selected text to chatbot input (in quotes)
  - User can then ask specific questions
- **Works on**: All text content (titles, body, key points, timeline, etc.)

### Module Navigation Flow
1. **Initial Load**: Loads module from localStorage or defaults to module 0
2. **Module Switch**: 
   - Updates all content dynamically
   - Preserves notes per module
   - Scrolls to top
   - Updates navigation state
3. **State Management**: 
   - Current module index persisted
   - Notes stored with module-specific keys
   - Format: `notes-module-{index}`

## Data Flow

### Module Loading Process
```
User Action (select/prev/next)
  ↓
loadModule(index)
  ↓
Update DOM Elements:
  - Title
  - Video embed
  - Explanation text
  - Key points (with audio controls)
  - Timeline events (with audio controls)
  - Fun fact
  - Interactive element
  ↓
Initialize Audio Sources
  ↓
Load Saved Notes
  ↓
Update Navigation UI
  ↓
Save Current Module Index
```

### Notes System
- **Storage**: `localStorage.setItem('notes-module-{index}', content)`
- **Retrieval**: `localStorage.getItem('notes-module-{index}')`
- **Auto-save**: On every input change
- **Isolation**: Each module has independent notes

### Chatbot Flow
```
User highlights text
  ↓
"Ask Gemini" button appears
  ↓
User clicks button
  ↓
Selected text added to input (quoted)
  ↓
User types question
  ↓
Send → API call to Gemini 2.0 Flash
  ↓
Response displayed in chat
  ↓
Conversation history maintained
```

## Styling & Design

### Theme
- **Dark Mode**: Primary color scheme
- **Glassmorphism**: Frosted glass effects on panels
- **Gradient Accents**: Blue-to-purple gradients
- **Modern UI**: Rounded corners, smooth shadows, hover effects
- **Responsive**: Mobile-optimized layouts

### Visual Hierarchy
- Section titles with underline accents
- Card-based content blocks
- Consistent spacing and padding
- Color-coded interactive elements

## Technical Implementation

### Single File Architecture
- All HTML, CSS, and JavaScript in one file
- No external dependencies (except YouTube API)
- Self-contained and portable

### API Integration
- **Gemini API**: Direct client-side calls
- **YouTube Embed**: Standard iframe embed
- **No Backend Required**: Fully client-side

### Browser Features Used
- localStorage for persistence
- Selection API for text highlighting
- Audio API for playback
- Fetch API for Gemini requests

## Module Creation Workflow

1. **Define Module Object**: Create object with all required properties
2. **Add to Modules Array**: `modules.push(newModule)` or use `addModule()`
3. **Set Audio Sources**: Populate `audioSources` object with URLs
4. **Update Selector**: Dropdown auto-updates when modules added
5. **Test Navigation**: Verify content loads correctly

## Key Functions

- `initModules()`: Initialize module system on page load
- `loadModule(index)`: Load and display specific module
- `updateNavigation()`: Update prev/next button states
- `setModules(newModules)`: Replace entire module array
- `addModule(module)`: Add single module to array
- `setupAudioControl(button, audioId)`: Initialize audio playback
- `setAudioSources(sources)`: Configure audio files
- `updateTimeline(events)`: Dynamically render timeline

## Use Cases

- **Educational Courses**: Multi-module learning paths
- **Training Materials**: Interactive corporate training
- **Documentation**: Step-by-step guides with media
- **Tutorials**: Progressive skill-building content

## Extensibility

- Easy to add new sections
- Flexible content injection
- Modular audio system
- Customizable styling via CSS variables
- Plugin-ready architecture
