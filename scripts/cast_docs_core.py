#!/usr/bin/env python3
from __future__ import annotations

# Compatibility facade: existing scripts import this module directly while the
# implementation lives in focused cast_docs_* modules.
from cast_docs_common import *  # noqa: F401,F403
from cast_docs_context import *  # noqa: F401,F403
from cast_docs_inline import *  # noqa: F401,F403
from cast_docs_svg import *  # noqa: F401,F403
from cast_docs_theme import *  # noqa: F401,F403
from cast_docs_validation import *  # noqa: F401,F403
from cast_docs_profile import *  # noqa: F401,F403
from cast_docs_renderer import *  # noqa: F401,F403
from cast_docs_html_profile import *  # noqa: F401,F403
from cast_docs_cli import *  # noqa: F401,F403

# Private names that existed on the old module and may be useful in local tests.
from cast_docs_renderer import _BLOCK_RENDERER_MAP_CACHE  # noqa: F401
from cast_docs_theme import _merge_theme  # noqa: F401
