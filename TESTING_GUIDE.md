# Testing Guide

Quick reference for testing the course system manually and with Playwright.

## Prerequisites

```bash
# Start local server (required!)
cd /Users/danielntumba/match-me/GeminiLoop
python -m http.server 8080
```

Then open: http://localhost:8080/index.html

## Manual Testing Checklist

### Course Hub (`index.html`)

- [ ] **Load Test**: Page loads without errors
- [ ] **Course Info**: Title and subtitle display correctly
- [ ] **Module Cards**: All 3 modules visible with correct titles
- [ ] **Module Links**: Clicking a module opens the correct page
- [ ] **Progress Bar**: Shows 0% initially
- [ ] **Reset Button**: Exists and is clickable
- [ ] **Toast**: Hidden initially
- [ ] **Responsive**: Works on mobile viewport (375px)

### Module 01 (`modules/module-01.html`)

**Hero Section:**
- [ ] Title displays: "What is Machine Learning?"
- [ ] Learning goals list visible
- [ ] Start button (`#startBtn`) scrolls to first section

**Background & Story:**
- [ ] Timeline has 3 milestones
- [ ] Clicking milestone expands details
- [ ] Timeline markers animate on hover
- [ ] Next/Prev buttons navigate sections

**Core Concept:**
- [ ] Definition card displays
- [ ] 8 vocabulary chips render
- [ ] Chips are clickable
- [ ] Misconception callout visible

**Visual Model:**
- [ ] 3 hotspots (A, B, C) visible
- [ ] Clicking hotspot updates explanation panel
- [ ] Reset button clears explanation
- [ ] Toast shows "Model reset"

**Worked Example:**
- [ ] Shows "Step 1 of 3"
- [ ] Next button advances steps
- [ ] Prev button disabled on step 1
- [ ] Delta summary updates per step
- [ ] Next button disabled on step 3

**Simulation:**
- [ ] Slider moves and updates value display
- [ ] Toggle switch works
- [ ] Apply button updates bars
- [ ] Explanation text changes
- [ ] Toast shows "Changes applied"
- [ ] Reset button works
- [ ] Toast shows "Simulation reset"

**Checkpoint:**
- [ ] Question displays
- [ ] 4 radio options present
- [ ] Check button validates answer
- [ ] Correct answer (B) shows success feedback
- [ ] Wrong answer shows error feedback
- [ ] Feedback has aria-live region

**Resources:**
- [ ] YouTube input field present
- [ ] Load button present
- [ ] Clear button present
- [ ] Invalid URL shows error (NO alert!)
- [ ] Valid YouTube URL loads iframe
- [ ] Resources list displays 2 default items
- [ ] Resource links open in new tab

**Summary:**
- [ ] Key takeaways display
- [ ] Completion button present
- [ ] Clicking completion:
  - [ ] Shows toast "Module completed!"
  - [ ] Redirects to hub after 1 second
  - [ ] Hub shows module as complete (checkmark)
  - [ ] Progress bar updates

**Keyboard Shortcuts:**
- [ ] `J` key advances section
- [ ] `K` key goes back section
- [ ] `Esc` key (no panels to close in this module)

### Modules 02 & 03

Repeat the above tests for:
- `modules/module-02.html` - Understanding Neural Networks
- `modules/module-03.html` - Training Your First Model

Check that:
- [ ] Content is different from Module 01
- [ ] Checkpoint questions are module-specific
- [ ] All IDs are identical (structure preserved)

### Progress Tracking

1. Complete all 3 modules
2. Check hub shows 100% progress
3. All module cards have checkmarks
4. Click "Reset Progress"
5. Progress returns to 0%
6. Checkmarks disappear
7. Toast shows "Progress reset successfully"

## Playwright Test Examples

### Test Course Hub

```javascript
const { test, expect } = require('@playwright/test');

test('course hub loads and displays modules', async ({ page }) => {
  await page.goto('http://localhost:8080/index.html');
  
  // Check hub elements
  await expect(page.locator('#hubTitle')).toBeVisible();
  await expect(page.locator('#modulesGrid')).toBeVisible();
  
  // Check module count
  const moduleCards = page.locator('.module-card');
  await expect(moduleCards).toHaveCount(3);
  
  // Check progress bar
  const progressBar = page.locator('#progressBarFill');
  await expect(progressBar).toHaveAttribute('style', /width: 0%/);
});

test('reset progress button works', async ({ page }) => {
  await page.goto('http://localhost:8080/index.html');
  
  // Click reset button
  await page.click('#resetProgressBtn');
  
  // Check toast appears
  await expect(page.locator('#toast')).toHaveClass(/visible/);
  await expect(page.locator('#toast')).toContainText('Progress reset');
});
```

### Test Module Navigation

```javascript
test('module start button scrolls to first section', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  await page.click('#startBtn');
  
  // Check toast appears
  await expect(page.locator('#toast')).toHaveClass(/visible/);
  
  // Verify scroll happened (background section should be visible)
  const bgSection = page.locator('#section-background');
  await expect(bgSection).toBeInViewport();
});

test('next/prev navigation works', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  // Start module
  await page.click('#startBtn');
  
  // Click next
  await page.click('#nextBtn');
  
  // Check second section visible
  const conceptSection = page.locator('#section-concept');
  await expect(conceptSection).toBeInViewport();
  
  // Click prev
  await page.click('#prevBtn');
  
  // Back to first section
  const bgSection = page.locator('#section-background');
  await expect(bgSection).toBeInViewport();
});
```

### Test Interactive Components

```javascript
test('hotspots update explanation panel', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  // Navigate to model section
  await page.click('#startBtn');
  await page.click('#nextBtn'); // to concept
  await page.click('.nav-next'); // to model
  
  // Click hotspot A
  await page.click('#hotspotA');
  
  // Check explanation updated
  const explanation = page.locator('#modelExplanation');
  await expect(explanation).toContainText('Data Collection');
  
  // Click reset
  await page.click('#modelResetBtn');
  
  // Check reset message
  await expect(explanation).toContainText('Click a hotspot');
  
  // Check toast
  await expect(page.locator('#toast')).toContainText('Model reset');
});

test('simulation controls work', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  // Navigate to simulation section
  // ... navigation code ...
  
  // Move slider
  await page.fill('#simSlider', '75');
  
  // Check value display updated
  await expect(page.locator('#sliderValue')).toContainText('75');
  
  // Toggle feature engineering
  await page.check('#simToggle');
  
  // Apply changes
  await page.click('#simApplyBtn');
  
  // Check toast
  await expect(page.locator('#toast')).toContainText('Changes applied');
  
  // Check bars updated
  const bar1 = page.locator('#bar1');
  const height = await bar1.evaluate(el => el.style.height);
  expect(parseFloat(height)).toBeGreaterThan(50); // Should increase from 50%
});
```

### Test Checkpoint

```javascript
test('checkpoint validates answers', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  // Navigate to checkpoint
  // ... navigation code ...
  
  // Select wrong answer
  await page.check('input[name="q1"][value="a"]');
  await page.click('#checkpointCheckBtn');
  
  // Check error feedback
  const feedback = page.locator('#checkpointFeedback');
  await expect(feedback).toHaveClass(/feedback-error/);
  await expect(feedback).toBeVisible();
  
  // Select correct answer
  await page.check('input[name="q1"][value="b"]');
  await page.click('#checkpointCheckBtn');
  
  // Check success feedback
  await expect(feedback).toHaveClass(/feedback-success/);
  await expect(feedback).toContainText('Correct!');
});
```

### Test YouTube Embed

```javascript
test('youtube embed validates URLs', async ({ page }) => {
  await page.goto('http://localhost:8080/modules/module-01.html');
  
  // Navigate to resources section
  // ... navigation code ...
  
  // Test invalid URL
  await page.fill('#embedInput', 'https://example.com/video');
  await page.click('#loadEmbedBtn');
  
  // Check error (NO alert - must be in DOM)
  const error = page.locator('#embedError');
  await expect(error).toBeVisible();
  await expect(error).toContainText('Invalid YouTube URL');
  
  // Test valid URL
  await page.fill('#embedInput', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  await page.click('#loadEmbedBtn');
  
  // Check iframe loaded
  const iframe = page.locator('#embedArea iframe');
  await expect(iframe).toBeVisible();
  await expect(iframe).toHaveAttribute('src', /youtube\.com\/embed/);
  
  // Check toast
  await expect(page.locator('#toast')).toContainText('Video loaded');
});
```

### Test Completion Flow

```javascript
test('completing module updates hub', async ({ page, context }) => {
  // Open hub in first tab
  const hubPage = await context.newPage();
  await hubPage.goto('http://localhost:8080/index.html');
  
  // Check initial progress
  await expect(hubPage.locator('#progressPercent')).toContainText('0%');
  
  // Open module in second tab
  const modulePage = await context.newPage();
  await modulePage.goto('http://localhost:8080/modules/module-01.html');
  
  // Navigate to summary (last section)
  // ... navigation code ...
  
  // Click completion button
  await modulePage.click('#completionBtn');
  
  // Check toast
  await expect(modulePage.locator('#toast')).toContainText('Module completed');
  
  // Wait for redirect
  await modulePage.waitForURL('**/index.html');
  
  // Check progress updated on hub
  await hubPage.reload();
  await expect(hubPage.locator('#progressPercent')).toContainText('33%');
  
  // Check module card has checkmark
  const moduleCard = hubPage.locator('.module-card').first();
  await expect(moduleCard).toHaveClass(/completed/);
});
```

## Browser Console Checks

Open browser DevTools (F12) and verify:

### No Errors
```
✓ No JavaScript errors
✓ No 404s (all resources load)
✓ No CORS errors
✓ No CSP violations
```

### LocalStorage
```javascript
// Check progress storage
localStorage.getItem('course_progress')
// Should show: {"module-01": true, ...}
```

### Network Tab
```
✓ course.json loads (200 OK)
✓ Module HTML files load
✓ No external CDN requests
✓ YouTube iframes only load on demand
```

## Mobile Testing

Test on mobile viewport (DevTools or real device):

```
Viewport: 375x667 (iPhone SE)
- [ ] Hub layout adapts
- [ ] Module cards stack vertically
- [ ] Navigation buttons are touch-friendly
- [ ] Text is readable (no tiny fonts)
- [ ] Interactive elements have adequate tap targets
- [ ] Sidebars/modals work on mobile
```

## Accessibility Testing

Use browser DevTools Lighthouse:
- [ ] Run Accessibility audit
- [ ] Check for ARIA issues
- [ ] Verify keyboard navigation
- [ ] Test with screen reader (if available)

### Keyboard Navigation
- [ ] Tab through all interactive elements
- [ ] Enter/Space activate buttons
- [ ] Arrow keys work in radio groups
- [ ] Focus visible on all elements

## Common Issues

### "Failed to load course.json"
- **Cause**: Not using HTTP server
- **Fix**: Run `python -m http.server 8080`

### Progress not saving
- **Cause**: Private browsing or localStorage disabled
- **Fix**: Use normal browser mode

### Modules not clickable
- **Cause**: JavaScript error on hub
- **Fix**: Check browser console for errors

### YouTube embeds fail
- **Cause**: Invalid URL format
- **Fix**: Use standard YouTube URLs

## Performance Testing

Check that pages load quickly:
- [ ] Hub loads in < 1 second
- [ ] Modules load in < 1 second  
- [ ] No layout shift (CLS)
- [ ] Smooth scrolling and animations
- [ ] No lag on interactions

---

**Questions?** See [COURSE_STRUCTURE.md](COURSE_STRUCTURE.md) for more details.
