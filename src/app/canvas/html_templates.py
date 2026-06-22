"""HTML Jinja shells for Canvas ``html_report`` artifacts."""

from __future__ import annotations

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

DEFAULT_HTML_TEMPLATE = "default"
STAKEHOLDER_BRIEF_TEMPLATE = "stakeholder_brief"

KNOWN_HTML_TEMPLATES: frozenset[str] = frozenset(
    {
        DEFAULT_HTML_TEMPLATE,
        STAKEHOLDER_BRIEF_TEMPLATE,
    }
)


def resolve_html_template_path(template_name: str) -> Path:
    """Map ``template_name`` to a file under ``app/canvas/templates/``."""
    normalized = (template_name or DEFAULT_HTML_TEMPLATE).strip().lower()
    if normalized not in KNOWN_HTML_TEMPLATES:
        raise ValueError(
            f"Unknown template_name {template_name!r}; "
            f"choose from {sorted(KNOWN_HTML_TEMPLATES)}."
        )
    return _TEMPLATES_DIR / f"{normalized}.html.j2"
