"""Status derivation and rendering, split into `derive` (model) and `render`
(views). This module re-exports the public API so existing imports are unchanged.
"""
from .derive import (
    APPROVED,
    DOCUMENTS_DIR,
    build_index,
    build_status,
    completeness_report,
    derive_rag,
    load_corpus,
)
from .render import (
    render_badge_json,
    render_html,
    render_index_html,
    render_index_markdown,
    render_json,
    render_markdown,
)

__all__ = [
    "DOCUMENTS_DIR", "APPROVED",
    "build_status", "build_index", "completeness_report", "derive_rag", "load_corpus",
    "render_markdown", "render_json", "render_html",
    "render_index_markdown", "render_index_html", "render_badge_json",
]
