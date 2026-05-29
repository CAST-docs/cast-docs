from __future__ import annotations

import html
from typing import Any

from cast_docs_common import as_list, attr, esc, is_object, localized_value, text
from cast_docs_context import RenderContext, default_locale_for_context, tr
from cast_docs_inline import render_svg_text_variants, render_text
from cast_docs_svg import sanitize_svg


def svg_text(value: Any) -> str:
    return html.escape(text(value), quote=False)


def render_sequence_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    steps = as_list(block.get("source", {}).get("steps"))
    participants: list[Any] = []
    participant_keys: set[str] = set()
    for step in steps:
        if not is_object(step):
            continue
        for key in ("from", "to"):
            participant = step.get(key)
            participant_key = text(localized_value(participant, "en"))
            if participant_key and participant_key not in participant_keys:
                participant_keys.add(participant_key)
                participants.append(participant)
    width = max(620, 180 * max(1, len(participants)) + 120)
    top = 94
    row_height = 58
    height = max(260, top + 44 + row_height * len(steps))
    lane_by_key = {
        text(localized_value(participant, "en")): 80 + index * 180
        for index, participant in enumerate(participants)
    }
    defs = (
        "<defs><marker id=\"seq-arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    rows = [defs]
    lifeline_bottom = height - 24
    for participant in participants:
        key = text(localized_value(participant, "en"))
        x = lane_by_key.get(key, 80)
        rows.append(f"<rect x=\"{x - 56}\" y=\"22\" width=\"112\" height=\"34\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        rows.append(render_svg_text_variants(participant, ctx, f"x=\"{x}\" y=\"44\" text-anchor=\"middle\" font-size=\"13\" fill=\"#2f3439\""))
        rows.append(f"<line x1=\"{x}\" y1=\"56\" x2=\"{x}\" y2=\"{lifeline_bottom}\" stroke=\"#9aa1a8\" stroke-width=\"1\" stroke-dasharray=\"5 5\"></line>")
    for index, step in enumerate(steps):
        if not is_object(step):
            continue
        from_key = text(localized_value(step.get("from"), "en"))
        to_key = text(localized_value(step.get("to"), "en"))
        x1 = lane_by_key.get(from_key, 80)
        x2 = lane_by_key.get(to_key, x1 + 180)
        y = top + index * row_height
        label_y = y - 9
        rows.append(f"<line x1=\"{x1}\" y1=\"{y}\" x2=\"{x2}\" y2=\"{y}\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#seq-arrow)\"></line>")
        rows.append(render_svg_text_variants(step.get("label"), ctx, f"x=\"{(x1 + x2) / 2:.0f}\" y=\"{label_y}\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
        rows.append(f"<rect x=\"{x2 - 4}\" y=\"{y - 8}\" width=\"8\" height=\"26\" rx=\"3\" fill=\"#dce8f8\" stroke=\"#9aa1a8\"></rect>")
    aria = localized_value(block.get("title") or tr(ctx, "diagram.sequenceAria", "Sequence diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(rows)}</svg>"


def render_flow_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    nodes = as_list(source.get("nodes"))
    width = max(420, 220 * len(nodes))
    height = 180
    node_by_id = {node.get("id"): index for index, node in enumerate(nodes) if is_object(node)}
    defs = (
        "<defs><marker id=\"arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    parts = [defs]
    for edge in as_list(source.get("edges")):
        if not is_object(edge):
            continue
        start = node_by_id.get(edge.get("from"))
        end = node_by_id.get(edge.get("to"))
        if start is None or end is None:
            continue
        x1 = 80 + start * 220 + 120
        x2 = 80 + end * 220
        parts.append(f"<line x1=\"{x1}\" y1=\"82\" x2=\"{x2}\" y2=\"82\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#arrow)\"></line>")
        if edge.get("label"):
            parts.append(render_svg_text_variants(edge.get("label"), ctx, f"x=\"{(x1 + x2) / 2:.0f}\" y=\"66\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
    for index, node in enumerate(nodes):
        if not is_object(node):
            continue
        x = 80 + index * 220
        parts.append(f"<rect x=\"{x}\" y=\"54\" width=\"120\" height=\"56\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        parts.append(render_svg_text_variants(node.get("label"), ctx, f"x=\"{x + 60}\" y=\"87\" text-anchor=\"middle\" font-size=\"13\" fill=\"#2f3439\""))
    aria = localized_value(block.get("title") or tr(ctx, "diagram.flowAria", "Flow diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(parts)}</svg>"


def render_er_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    entities = [entity for entity in as_list(source.get("entities")) if is_object(entity)]
    width = max(760, 260 * len(entities) + 80)
    entity_width = 210
    card_tops: dict[str, tuple[int, int, int]] = {}
    heights = []
    for entity in entities:
        heights.append(66 + 24 * len(as_list(entity.get("fields"))))
    height = max(220, max(heights, default=120) + 96)
    defs = (
        "<defs><marker id=\"er-arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    parts = [defs]
    for index, entity in enumerate(entities):
        x = 44 + index * 260
        y = 46
        entity_height = 66 + 24 * len(as_list(entity.get("fields")))
        entity_id = text(entity.get("id"))
        card_tops[entity_id] = (x, y, entity_height)
        parts.append(f"<rect x=\"{x}\" y=\"{y}\" width=\"{entity_width}\" height=\"{entity_height}\" rx=\"8\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        parts.append(f"<rect x=\"{x}\" y=\"{y}\" width=\"{entity_width}\" height=\"38\" rx=\"8\" fill=\"#dce8f8\" stroke=\"#9aa1a8\"></rect>")
        parts.append(render_svg_text_variants(entity.get("name"), ctx, f"x=\"{x + 16}\" y=\"{y + 25}\" font-size=\"14\" fill=\"#2f3439\""))
        for field_index, field in enumerate(as_list(entity.get("fields"))):
            parts.append(render_svg_text_variants(field, ctx, f"x=\"{x + 16}\" y=\"{y + 60 + field_index * 24}\" font-size=\"12\" fill=\"#68717b\""))
    for relationship in as_list(source.get("relationships")):
        if not is_object(relationship):
            continue
        start = card_tops.get(text(relationship.get("from")))
        end = card_tops.get(text(relationship.get("to")))
        if not start or not end:
            continue
        x1, y1, h1 = start
        x2, y2, h2 = end
        sx = x1 + entity_width
        ex = x2
        sy = y1 + h1 + 30
        ey = y2 + h2 + 30
        bend_y = max(sy, ey) + 18
        parts.append(f"<polyline points=\"{sx},{sy} {sx},{bend_y} {ex},{bend_y} {ex},{ey}\" fill=\"none\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#er-arrow)\"></polyline>")
        if relationship.get("label"):
            parts.append(render_svg_text_variants(relationship.get("label"), ctx, f"x=\"{(sx + ex) / 2:.0f}\" y=\"{bend_y - 8}\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
    aria = localized_value(block.get("title") or tr(ctx, "diagram.erAria", "Entity relationship diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(parts)}</svg>"


def render_diagram(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    fmt = source.get("format")
    if fmt == "structured-sequence":
        svg = render_sequence_svg(block, ctx)
    elif fmt == "structured-flow":
        svg = render_flow_svg(block, ctx)
    elif fmt == "structured-er":
        svg = render_er_svg(block, ctx)
    elif fmt == "svg":
        svg, svg_errors = sanitize_svg(text(source.get("content")), "diagram.source.content")
        if svg_errors or svg is None:
            svg = f"<svg viewBox=\"0 0 320 100\" xmlns=\"http://www.w3.org/2000/svg\"><text x=\"20\" y=\"50\">{esc(tr(ctx, 'diagram.unsupported', 'Unsupported diagram'))}</text></svg>"
    else:
        svg = f"<svg viewBox=\"0 0 320 100\" xmlns=\"http://www.w3.org/2000/svg\"><text x=\"20\" y=\"50\">{esc(tr(ctx, 'diagram.unsupported', 'Unsupported diagram'))}</text></svg>"
    name = attr(block.get("downloadName") or "diagram")
    title = block.get("title")
    caption = f"<figcaption>{render_text(title, ctx)}</figcaption>" if title else ""
    return f"<figure class=\"diagram\" data-download-name=\"{name}\">{caption}{svg}</figure>"
