"""Render a parsed ``Lesson`` into Markdown via Jinja2.

The renderer is a thin wrapper around Jinja2 so callers do not have to know
about template paths or environments. The template ships as package data.
"""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, PackageLoader, select_autoescape

from app.lesson.models import Lesson


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=PackageLoader("app.lesson", "templates"),
        autoescape=select_autoescape(disabled_extensions=("md", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_lesson_markdown(lesson: Lesson) -> str:
    """Render a Lesson as Markdown. Falls back to ``lesson.raw`` when unstructured."""
    if not lesson.is_structured:
        return (lesson.raw or "").strip()
    template = _environment().get_template("lesson.md.j2")
    return template.render(lesson=lesson)
