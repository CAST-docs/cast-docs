# Interactive Features

CAST Docs is primarily a static, self-contained HTML document system. Interactions are allowed only as renderer-owned progressive enhancements with stable hooks and validation rules.

The MVP ships one interaction: diagram viewer (zoom / pan / SVG / PNG download).

## Principles

- Generated content must not author its own JavaScript.
- Approved interactions live in the shared base template and are versioned with the renderer.
- Interactions must degrade gracefully when unavailable.
- No external CDN, remote script, remote style, or runtime service is allowed.
- Interactive hooks must be semantic classes or data attributes approved by the HTML profile.

## Diagram Viewer And Download

Diagram components should support:

- Click to open a lightbox or enlarged viewer.
- Zoom in, zoom out, reset, pan, and close with Escape.
- One-click SVG download for inline SVG diagrams.
- One-click PNG download for inline SVG diagrams through renderer-owned script.

Supported diagram sources:

- Inline SVG generated from structured diagram blocks.
- Future renderer-produced diagrams that compile to inline SVG.

Out of scope by default:

- Remote images.
- CDN Mermaid runtime.
- User-authored JavaScript.
- Browser layout verification for every diagram.

The document JSON should describe diagram content and intent. The renderer should emit the approved diagram wrapper and controls.

Example block shape:

```json
{
  "type": "diagram",
  "kind": "sequence",
  "title": "Call chain",
  "downloadName": "call-chain",
  "source": {
    "format": "svg",
    "content": "<svg>...</svg>"
  }
}
```

The final schema may avoid raw SVG strings and use a safer structured diagram format. If raw SVG is allowed, it must pass the SVG subset validator.

## Configuration

Interactions should be declared in `config/interactions.json`.

Example:

```json
{
  "diagram-viewer": {
    "enabledByDefault": true,
    "templateHooks": ["diagram", "diagram-toolbar", "lightbox"],
    "requiresScript": true
  }
}
```
