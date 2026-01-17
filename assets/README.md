# Assets Directory

This directory contains shared media, data, and manifest files for the course modules.

## Directory Structure

```
assets/
├── README.md               (this file)
├── embeds/                 (embed manifests)
│   └── youtube.json        (YouTube video references by module)
├── resources/              (learning resource manifests)
│   └── resources.json      (curated resources by module)
├── images/                 (shared images - optional)
├── audio/                  (shared audio files - optional)
├── video/                  (shared video files - optional)
└── data/                   (datasets, sample files - optional)
```

## What Goes Here

### Embeds (`/embeds/`)
JSON manifests mapping module IDs to embeddable content (e.g., YouTube videos). Each entry includes:
- URL (YouTube link)
- Start time (optional)
- Title
- Description/notes

### Resources (`/resources/`)
JSON manifests mapping module IDs to curated learning resources. Each resource includes:
- Title
- URL
- Type (article, video, course, tutorial, documentation)
- Level (beginner, intermediate, advanced)
- Description
- Tags

### Media Files
Optionally store shared images, audio, or video files that multiple modules reference. Individual modules are self-contained, so this is only for truly shared assets.

### Data Files
Sample datasets, configuration files, or other data referenced by modules.

## Naming Conventions

- Use kebab-case for file names: `my-dataset.csv`
- Prefix module-specific files with module ID: `module-01-diagram.svg`
- Use descriptive names: `neural-network-architecture.png` not `img1.png`

## Important Notes

1. **Modules are self-contained**: Each module HTML file includes all inline CSS and JS. Assets here are optional supplements.
2. **No external dependencies**: Don't link to external CDNs or libraries.
3. **Relative paths**: Reference assets using relative paths from module files: `../assets/images/diagram.png`
4. **Git-friendly**: Keep binary files small (<1MB when possible). Use `.gitignore` for large files.

## Adding New Assets

1. Place files in the appropriate subdirectory
2. Update manifests (youtube.json, resources.json) as needed
3. Reference from modules using relative paths
4. Document any special usage requirements here

## Manifest Formats

### youtube.json Example
```json
{
  "module-01": {
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "start_seconds": 0,
    "title": "Introduction to ML",
    "notes": "Official course intro video"
  }
}
```

### resources.json Example
```json
{
  "module-01": [
    {
      "title": "ML Crash Course",
      "url": "https://example.com/course",
      "type": "course",
      "level": "beginner",
      "description": "Comprehensive intro to ML",
      "tags": ["supervised-learning", "python"]
    }
  ]
}
```
