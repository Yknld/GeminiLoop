# Course Structure Documentation

This document describes the new modular course architecture implemented in GeminiLoop.

## Architecture Overview

The course system uses a hub-and-spoke architecture:
- **Hub (`index.html`)**: Central course page with module navigation and progress tracking
- **Modules (`modules/*.html`)**: Self-contained learning modules with inline CSS/JS
- **Assets (`assets/`)**: Shared manifests for embeds and resources
- **Course Plan (`course.json`)**: Metadata defining the course structure

## Directory Structure

```
GeminiLoop/
├── index.html                      # Course hub (main landing page)
├── course.json                     # Course plan with module metadata
├── modules/                        # Self-contained module pages
│   ├── module-01.html             # Module: What is Machine Learning?
│   ├── module-02.html             # Module: Understanding Neural Networks
│   └── module-03.html             # Module: Training Your First Model
├── assets/                        # Shared resources and manifests
│   ├── README.md                  # Asset guidelines
│   ├── embeds/
│   │   └── youtube.json          # YouTube embed references
│   └── resources/
│       └── resources.json        # Curated learning resources
└── legacy/                        # Archived old templates
    └── old-template.html         # Original single-file template
```

## Running Locally

**Important**: The course requires a local HTTP server to load JSON files. File protocol (`file://`) will not work.

### Quick Start

```bash
cd GeminiLoop

# Option 1: Python's built-in server
python -m http.server 8080

# Option 2: Node.js http-server
npx http-server -p 8080

# Option 3: PHP's built-in server
php -S localhost:8080
```

Then open http://localhost:8080 in your browser.

## Course Hub (`index.html`)

The hub is the entry point for learners:

### Features
- **Module Grid**: Visual cards for each module showing title, goals, and time estimate
- **Progress Tracking**: Percentage completion based on localStorage
- **Module Status**: Visual indicators for completed modules
- **Reset Progress**: Clear all completion data

### Required IDs (for testing)
- `#hubTitle` - Course title
- `#hubSubtitle` - Course subtitle
- `#modulesGrid` - Container for module cards
- `#resetProgressBtn` - Reset progress button
- `#toast` - Toast notification element

### LocalStorage Contract
Progress is stored in localStorage under the key `course_progress`:
```json
{
  "module-01": true,
  "module-02": false,
  "module-03": true
}
```

## Course Plan (`course.json`)

Defines the course metadata and module list:

```json
{
  "course_title": "Introduction to Machine Learning",
  "course_subtitle": "Master the fundamentals...",
  "audience_level": "Beginner",
  "estimated_total_minutes": 120,
  "modules": [
    {
      "id": "module-01",
      "title": "What is Machine Learning?",
      "slug": "modules/module-01.html",
      "goals": ["Goal 1", "Goal 2", "Goal 3"],
      "estimated_minutes": 30,
      "status": "ready",
      "embed_ref": "module-01-intro",
      "resources_ref": "module-01"
    }
  ]
}
```

## Module Structure

Each module is a standalone HTML file with inline CSS and JavaScript. No external dependencies.

### Module Sections

Every module contains these sections in order:

#### A) Hero
- Module number and title
- Learning goals list
- Start button (`#startBtn`)

#### B) Background & Story
- Historical context
- Expandable timeline with 3+ milestones (`#milestone-1`, `#milestone-2`, `#milestone-3`)

#### C) Core Concept
- Definition and explanation
- Vocabulary chips (interactive terms)
- Common misconception callout

#### D) Visual Model
- Interactive diagram with clickable hotspots (`#hotspotA`, `#hotspotB`, `#hotspotC`)
- Explanation panel (`#modelExplanation`)
- Reset button (`#modelResetBtn`)

#### E) Worked Example
- Multi-step walkthrough (`#examplePanel`)
- Step navigation (`#examplePrevStepBtn`, `#exampleNextStepBtn`)
- Delta summary showing what changed (`#exampleDelta`)

#### F) Try It / Simulation
- Interactive controls (`#simSlider`, `#simToggle`)
- Visual feedback (`#simViz`)
- Apply and reset buttons (`#simApplyBtn`, `#simResetBtn`)
- Explanation panel (`#simExplanation`)

#### G) Checkpoint
- One or more questions
- DOM-based feedback (`#checkpointFeedback` with `aria-live`)
- Check answer button (`#checkpointCheckBtn`)

#### H) Resources
- YouTube embed interface (`#embedInput`, `#loadEmbedBtn`, `#clearEmbedBtn`, `#embedArea`)
- URL validation (YouTube only)
- Error display (`#embedError` with `aria-live`)
- Resource list (`#resourcesList`) loaded from `assets/resources/resources.json`

#### I) Summary & Completion
- Key takeaways recap
- Completion button (`#completionBtn`)
- Returns to hub and marks module complete in localStorage

### Module Required IDs

For Playwright testing, each module must have these stable IDs:

**General Navigation:**
- `#startBtn` - Start learning button
- `#nextBtn` - Next section button
- `#prevBtn` - Previous section button
- `#toast` - Toast notification element
- `#completionBtn` - Mark complete button

**Timeline:**
- `#timeline` - Timeline container
- `#milestone-1`, `#milestone-2`, `#milestone-3` - Expandable timeline items

**Visual Model:**
- `#hotspotA`, `#hotspotB`, `#hotspotC` - Interactive hotspots
- `#modelExplanation` - Explanation panel
- `#modelResetBtn` - Reset button

**Worked Example:**
- `#examplePrevStepBtn` - Previous step
- `#exampleNextStepBtn` - Next step
- `#examplePanel` - Content panel
- `#exampleDelta` - Delta summary

**Simulation:**
- `#simSlider` - Range input
- `#simToggle` or `#simSelect` - Toggle switch or dropdown
- `#simApplyBtn` - Apply changes
- `#simResetBtn` - Reset simulation
- `#simViz` - Visualization area

**Checkpoint:**
- `#checkpointCheckBtn` - Check answer
- `#checkpointFeedback` - Feedback display (aria-live)

**Resources/Embeds:**
- `#embedInput` - YouTube URL input
- `#loadEmbedBtn` - Load embed button
- `#clearEmbedBtn` - Clear embed button
- `#embedArea` - Embed container
- `#embedError` - Error display (aria-live)
- `#resourcesList` - Resources list

### Navigation Between Sections

Modules use internal navigation:
- **Next/Previous buttons**: Move between sections within the module
- **Keyboard shortcuts**: `J` (next), `K` (previous), `Esc` (close panels)
- **Smooth scrolling**: Sections use `scroll-margin-top` for proper positioning

### YouTube Embedding

Security rules for embedding:
1. Only YouTube URLs are allowed
2. URLs must match patterns:
   - `youtube.com/watch?v=VIDEO_ID`
   - `youtu.be/VIDEO_ID`
   - `youtube.com/embed/VIDEO_ID`
3. Converted to: `https://www.youtube.com/embed/VIDEO_ID`
4. Not auto-loaded - user must click "Load"
5. Invalid URLs show DOM error (NO alert/confirm/prompt)

## Assets System

### Embeds Manifest (`assets/embeds/youtube.json`)

Maps module references to YouTube videos:

```json
{
  "module-01-intro": {
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "start_seconds": 0,
    "title": "Video Title",
    "notes": "Description"
  }
}
```

### Resources Manifest (`assets/resources/resources.json`)

Maps module IDs to curated resources:

```json
{
  "module-01": [
    {
      "title": "Resource Title",
      "url": "https://example.com",
      "type": "course",
      "level": "beginner",
      "description": "One-line description",
      "tags": ["tag1", "tag2"]
    }
  ]
}
```

## Design Principles

### No External Dependencies
- No CDNs
- No external CSS/JS files
- All styles inline in `<style>` tags
- All scripts inline in `<script>` tags

### DOM-Based Feedback
- **NO** `alert()`, `confirm()`, or `prompt()`
- **YES** toast notifications, inline messages, `aria-live` regions
- All feedback must be visible in the DOM

### Accessibility
- Proper ARIA labels and roles
- Keyboard navigation support
- Focus management
- Screen reader friendly

### Mobile-Friendly
- Responsive design
- Touch-friendly controls
- Mobile breakpoints in CSS
- No hover-only interactions

### Progress Tracking
- Uses localStorage
- Module completion persisted
- No server required
- Privacy-friendly (no external tracking)

## Testing

### Manual Testing Checklist

**Course Hub:**
- [ ] Modules load and display correctly
- [ ] Progress bar updates when modules completed
- [ ] Reset button clears progress
- [ ] Module links navigate to correct pages
- [ ] Toast notifications appear

**Each Module:**
- [ ] Start button scrolls to first section
- [ ] Next/Previous navigation works
- [ ] Timeline items expand/collapse
- [ ] Hotspots update explanation panel
- [ ] Example stepper advances through steps
- [ ] Simulation controls update visualization
- [ ] Checkpoint shows feedback
- [ ] YouTube embed validates URLs
- [ ] Resource list displays
- [ ] Completion button marks module complete
- [ ] Keyboard shortcuts work (J/K/Esc)

### Automated Testing (Playwright)

Use the stable IDs to write automated tests:

```javascript
// Example test
await page.goto('http://localhost:8080/modules/module-01.html');
await page.click('#startBtn');
await page.click('#nextBtn');
await page.click('#hotspotA');
await expect(page.locator('#modelExplanation')).toBeVisible();
```

## Customization

### Adding a New Module

1. **Duplicate an existing module:**
   ```bash
   cp modules/module-01.html modules/module-04.html
   ```

2. **Update MODULE_ID in JavaScript:**
   ```javascript
   const MODULE_ID = 'module-04';
   ```

3. **Update content:**
   - Hero title and goals
   - Section content
   - Timeline milestones
   - Vocabulary terms
   - Example steps
   - Checkpoint questions

4. **Add to course.json:**
   ```json
   {
     "id": "module-04",
     "title": "Your New Module",
     "slug": "modules/module-04.html",
     "goals": ["Goal 1", "Goal 2"],
     "estimated_minutes": 30,
     "status": "ready"
   }
   ```

5. **Add resources (optional):**
   - Update `assets/resources/resources.json`
   - Update `assets/embeds/youtube.json`

### Customizing Styles

All CSS is inline in each module's `<style>` tag. Key variables:

```css
:root {
  --color-primary: #4f46e5;      /* Main brand color */
  --color-success: #059669;       /* Success feedback */
  --color-warning: #d97706;       /* Warnings */
  --color-error: #dc2626;         /* Errors */
  --spacing-xl: 2rem;             /* Large spacing */
  --radius-lg: 0.5rem;            /* Border radius */
}
```

## Troubleshooting

### "Failed to load course.json"
- Ensure you're running a local HTTP server
- Check that `course.json` exists in the root directory
- Open browser console for detailed error messages

### Progress not saving
- Check browser's localStorage permissions
- Try clearing localStorage and resetting progress
- Some browsers block localStorage in private/incognito mode

### YouTube embeds not loading
- Verify the URL format is correct
- Check for CORS or CSP restrictions
- Ensure the video is publicly accessible

### Modules not displaying correctly
- Check browser console for JavaScript errors
- Verify all required IDs are present
- Test in different browsers

## Migration from Legacy Template

The original single-file template has been moved to `legacy/old-template.html`. To migrate custom content:

1. Identify your custom sections in the old template
2. Map content to the new module structure
3. Update IDs to match the required stable IDs
4. Split long content across multiple modules
5. Test all interactive features

## Future Enhancements

Potential additions:
- [ ] Progress export/import
- [ ] Certificate generation
- [ ] Discussion forums integration
- [ ] Video transcripts
- [ ] Downloadable PDFs
- [ ] Quiz randomization
- [ ] Gamification (badges, points)
- [ ] Multi-language support

## Questions?

For issues or questions about the course structure:
1. Check this documentation
2. Review `assets/README.md` for asset guidelines
3. Open an issue in the repository
4. Check the browser console for errors

---

**Last Updated**: January 2026
