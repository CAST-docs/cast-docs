from __future__ import annotations

# Compatibility facade for renderer helpers. Concrete renderers live in focused
# modules so individual files stay reviewable.
from cast_docs_renderer_diagrams import *  # noqa: F401,F403
from cast_docs_renderer_blocks import *  # noqa: F401,F403
from cast_docs_renderer_shell import *  # noqa: F401,F403

from cast_docs_renderer_blocks import _BLOCK_RENDERER_MAP_CACHE  # noqa: F401
