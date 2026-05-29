from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cast_docs_core import render_html, sanitize_svg, validate_document  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
