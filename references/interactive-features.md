# Interactive Features

CAST Docs is primarily a static, self-contained HTML document system. Interactions are allowed only as renderer-owned progressive enhancements with stable hooks and validation rules.

The built-in interactions are diagram viewer, code copy, language switching, toggle view, and slider control. They are renderer-owned scripts selected from `config/interactions.json` based on layout and block types.

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

## Code Copy

Code and action prompt blocks render a copy button in their header. The script copies the text from `.code-line-content`, ignoring line numbers and using the currently active locale when the code body is localized.

The document JSON does not author copy JavaScript. It only provides the code string and optional language label.

## Toggle View

The `toggle-view` block renders a segmented button group and one panel per view. Buttons use `data-view-target`; panels use `data-view-panel` and `data-view-active`.

Use this for controlled view switching such as overview/source, table/chart, or before/after content. Do not add event-handler attributes or custom scripts to generated content.

## Slider Control

The `slider` block renders a renderer-owned range input, output value, and preview target. The control uses `data-slider-target`, `data-slider-output`, and `data-slider-demo`; the shared script updates the output and applies the selected effect to the target. The initial supported effect is `opacity`, useful for examples such as making text brighter or dimmer without content-authored JavaScript.

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
