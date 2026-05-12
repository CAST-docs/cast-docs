# HTML Profile

CAST Docs uses a controlled HTML subset. The goal is deterministic document output, not arbitrary web page generation.

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
- `article`, `header`, `nav`, `main`, `section`, `footer`
- `h1`, `h2`, `h3`, `p`, `a`, `strong`, `em`, `code`, `pre`
- `ul`, `ol`, `li`
- `table`, `thead`, `tbody`, `tr`, `th`, `td`
- `dl`, `dt`, `dd`
- `aside`, `details`, `summary`, `figure`, `figcaption`
- `svg`, `g`, `path`, `rect`, `circle`, `line`, `polyline`, `polygon`, `text`, `defs`, `marker`

## Disallowed Tags

- `script`
- `iframe`
- `object`
- `embed`
- `link`
- `video`
- `audio`
- `canvas`
- `form`
- `input`
- `button`
- `textarea`
- `select`

## Disallowed Attributes

- Event handlers such as `onclick`, `onload`, `onerror`, and `onmouseover`.
- Inline `style`.
- Remote resource attributes by default.
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

Do not generate random utility classes or Tailwind-style class lists.
