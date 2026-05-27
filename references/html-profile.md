# HTML Profile

CAST Docs uses a controlled HTML subset. The goal is deterministic document output, not arbitrary web page generation.

All generated documents must share the same base structure, class vocabulary, style system, and approved interaction model. Document-specific styling should be represented through approved semantic classes, not one-off CSS.

The renderer owns the shared template, style system, and approved progressive-enhancement scripts. Generation should not copy the full template into the prompt context, and should not introduce external scripts, CDNs, fonts, images, or runtime services.

Content blocks must not emit `<script>`. Renderer-owned inline scripts are allowed only when they implement approved template features such as diagram zoom/download, code copy, language switching, and toggle views.

Theme tokens and layout shells are configuration-driven. Generated content should not introduce new CSS variables, layout containers, or navigation chrome outside the selected layout.

## Required Structure

- Complete `<!doctype html>` document.
- `<html lang="zh-CN">` by default unless the user asks for English.
- `<meta charset="utf-8">`.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- Meaningful `<title>`.
- Inline `<style>`.
- `<article class="doc">`.
- Document header.
- Table of contents.
- Stable section IDs.
- Footer with document metadata.

## Allowed Tags

Planned allowed tags:

- `html`, `head`, `meta`, `title`, `style`, `body`
- renderer-owned `script`
- renderer-owned `button`
- `article`, `header`, `nav`, `main`, `section`, `footer`
- `h1`, `h2`, `h3`, `p`, `a`, `strong`, `em`, `code`, `pre`, `del`, `u`, `mark`
- `ul`, `ol`, `li`
- `table`, `thead`, `tbody`, `tr`, `th`, `td`
- `dl`, `dt`, `dd`
- `aside`, `details`, `summary`, `figure`, `figcaption`, `img`
- `svg`, `g`, `path`, `rect`, `circle`, `line`, `polyline`, `polygon`, `text`, `defs`, `marker`

## Disallowed Tags

- user-content `script`
- `iframe`
- `object`
- `embed`
- `link`
- `video`
- `audio`
- `canvas`
- `form`
- `input`
- user-content `button`
- `textarea`
- `select`

## Disallowed Attributes

- Event handlers such as `onclick`, `onload`, `onerror`, and `onmouseover`.
- Inline `style`.
- Remote resource attributes by default, except approved media `src` values (`data:image`, relative paths, or http(s) sources) validated by the media block contract.
- `href` values starting with `javascript:`.

## Class Naming

Use stable semantic classes such as:

- `doc`
- `doc-header`
- `doc-kicker`
- `doc-summary`
- `doc-meta`
- `toc`
- `doc-section`
- `callout`
- `callout-info`
- `callout-warning`
- `callout-danger`
- `data-table`
- `risk-table`
- `decision-table`
- `status-pill`
- `section-empty`
- `doc-footer`
- `diagram`
- `diagram-toolbar`
- `svg-figure`
- `lightbox`
- `lightbox-panel`
- `lightbox-body`
- `lightbox-toolbar`
- `lightbox-close`
- `code-shell`, `code-header`, `code-copy`, `code-line`
- `diff-code`, `diff-line`, `line-highlight`
- `media-grid`, `media-frame`
- `columns`, `column`
- `toggle-view`, `toggle-toolbar`, `toggle-panel`

Do not generate random utility classes or Tailwind-style class lists.

## Inline Marks

Inline semantic marks use the `data-mark` attribute (`deprecated`, `term`, `metric`) rather than CSS classes; visual marks use the `del`, `u`, and `mark` tags. Inline `code` may carry `data-mark="ref"` for a code reference. No new classes are introduced for inline formatting.
