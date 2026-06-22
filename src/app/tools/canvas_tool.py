"""ADK ``produce_structured_canvas`` - Jinja2 + Markdown artifact tool."""

from __future__ import annotations

import json

import markdown as md_lib
from jinja2 import Environment, StrictUndefined, select_autoescape
from markupsafe import Markup
from pydantic import ValidationError

from app.canvas.html_templates import resolve_html_template_path
from app.canvas.models import CanvasProduceInput


def make_canvas_delivery_tool():
    """Factory returning a sync callable that ADK auto-wraps as a FunctionTool."""

    jinja = Environment(
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        undefined=StrictUndefined,
        loader=None,
    )

    def _html_template_for(name: str):
        path = resolve_html_template_path(name)
        return jinja.from_string(path.read_text(encoding="utf-8"))

    def produce_structured_canvas(
        output_kind: str,
        title: str,
        markdown_body: str,
        programming_language: str = "",
        template_name: str = "default",
    ) -> str:
        """Render a Canvas artifact (Markdown report, HTML wrapping, or code fence).

        Call this when the user explicitly asks for a deliverable artifact - a
        printable handout, stakeholder summary, or reproducible code snippet.
        For ``html_report``, set ``template_name`` to ``stakeholder_brief`` for a
        styled shell. The agent must populate ``markdown_body`` from validated
        prior context, not from memory.
        """
        try:
            payload = CanvasProduceInput(
                output_kind=output_kind.strip().lower(),
                title=title,
                markdown_body=markdown_body,
                programming_language=programming_language,
                template_name=template_name,
            )
        except ValidationError as exc:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"canvas_validation:{exc!s}",
                    "title": title,
                },
                ensure_ascii=False,
            )

        if payload.output_kind == "markdown_report":
            lines = [
                f"# {payload.title}".strip(),
                "",
                payload.markdown_body,
                "",
                "---",
                "_Canvas artifact (`markdown_report`)._",
            ]
            return json.dumps(
                {
                    "ok": True,
                    "mime": "text/markdown",
                    "output_kind": payload.output_kind,
                    "artifact": "\n".join(lines),
                },
                ensure_ascii=False,
            )

        if payload.output_kind == "html_report":
            body_html = Markup(
                md_lib.markdown(
                    payload.markdown_body,
                    extensions=["tables", "fenced_code"],
                )
            )
            html_template = _html_template_for(payload.template_name)
            html_doc = html_template.render(title=payload.title, body_html=body_html)
            return json.dumps(
                {
                    "ok": True,
                    "mime": "text/html",
                    "output_kind": payload.output_kind,
                    "template_name": payload.template_name,
                    "artifact": html_doc,
                },
                ensure_ascii=False,
            )

        lang = payload.programming_language
        fenced = (
            f"# {payload.title}\n\n"
            f"```{lang}\n{payload.markdown_body.rstrip()}\n```\n\n"
            "_Canvas artifact (`code_snippet`)._\n"
        )
        return json.dumps(
            {
                "ok": True,
                "mime": "text/markdown",
                "output_kind": payload.output_kind,
                "artifact": fenced,
                "programming_language": lang,
            },
            ensure_ascii=False,
        )

    return produce_structured_canvas
