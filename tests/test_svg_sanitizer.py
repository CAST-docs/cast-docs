from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cast_docs_core import load_config, render_html, sanitize_svg, validate_document, validate_html_profile  # noqa: E402


def base_doc(svg_content: str) -> dict[str, object]:
    return {
        "metadata": {
            "title": "SVG sanitizer test",
            "language": "en",
            "status": "draft",
            "owner": "tests",
        },
        "manifest": {
            "documentType": "engineering-spec",
            "scenario": "none",
            "sections": ["main"],
            "components": {
                "required": ["metadata-block", "toc", "section", "diagram"],
                "optional": [],
                "omitted": [],
            },
        },
        "sections": [
            {
                "id": "main",
                "title": "Main",
                "blocks": [
                    {
                        "type": "diagram",
                        "kind": "svg",
                        "source": {
                            "format": "svg",
                            "content": svg_content,
                        },
                    }
                ],
            }
        ],
    }


class SvgSanitizerTest(unittest.TestCase):
    def test_safe_svg_is_rebuilt_from_allowlist(self) -> None:
        source = '<svg viewBox="0 0 20 20"><title>Safe</title><circle cx="10" cy="10" r="4" fill="#111111"/></svg>'
        sanitized, errors = sanitize_svg(source)

        self.assertEqual(errors, [])
        self.assertIsNotNone(sanitized)
        self.assertIn("<circle", sanitized or "")
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', sanitized or "")

    def test_event_handler_svg_is_rejected(self) -> None:
        source = '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="4" onload="alert(1)"/></svg>'
        sanitized, errors = sanitize_svg(source)

        self.assertIsNone(sanitized)
        self.assertTrue(any("onload" in error for error in errors))

    def test_external_reference_svg_is_rejected(self) -> None:
        source = '<svg viewBox="0 0 20 20"><image href="https://example.com/a.png"/></svg>'
        sanitized, errors = sanitize_svg(source)

        self.assertIsNone(sanitized)
        self.assertTrue(any("<image>" in error for error in errors))

    def test_svg_declarations_are_rejected(self) -> None:
        source = '<?xml-stylesheet href="https://example.com/a.css"?><svg viewBox="0 0 20 20"></svg>'
        sanitized, errors = sanitize_svg(source)

        self.assertIsNone(sanitized)
        self.assertTrue(any("declarations" in error for error in errors))

    def test_document_validation_rejects_unsafe_svg(self) -> None:
        source = '<svg viewBox="0 0 20 20"><script>alert(1)</script></svg>'
        result = validate_document(base_doc(source))

        self.assertFalse(result.ok)
        self.assertTrue(any("<script>" in error for error in result.errors))

    def test_renderer_does_not_passthrough_unsafe_svg(self) -> None:
        source = '<svg viewBox="0 0 20 20"><script>alert(1)</script></svg>'
        html = render_html(base_doc(source))

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("Unsupported diagram", html)

    def test_document_validation_rejects_mermaid_code_blocks(self) -> None:
        doc = {
            "metadata": {
                "title": "Raw diagram source test",
                "language": "en",
                "status": "draft",
                "owner": "tests",
            },
            "manifest": {
                "documentType": "engineering-spec",
                "scenario": "none",
                "sections": ["main"],
                "components": {
                    "required": ["metadata-block", "toc", "section", "code-block"],
                    "optional": [],
                    "omitted": [],
                },
            },
            "sections": [
                {
                    "id": "main",
                    "title": "Main",
                    "blocks": [{"type": "code", "language": "mermaid", "code": "flowchart TD\nA --> B"}],
                }
            ],
        }

        result = validate_document(doc)

        self.assertFalse(result.ok)
        self.assertTrue(any("raw diagram source" in error for error in result.errors))

    def test_html_profile_rejects_raw_mermaid_blocks(self) -> None:
        html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>.doc{}</style><title>Test</title></head>
<body><article class="doc"><pre data-language="mermaid"><code data-language="mermaid">flowchart TD
A --> B</code></pre></article></body></html>"""

        result = validate_html_profile(html, load_config("html-profile.json"))

        self.assertFalse(result.ok)
        self.assertTrue(any("raw diagram source" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
