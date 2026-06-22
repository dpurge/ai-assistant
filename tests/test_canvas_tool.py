from __future__ import annotations

import json

from app.tools.canvas_tool import make_canvas_delivery_tool


def test_markdown_report_branch():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="markdown_report",
            title="Aspect cheatsheet",
            markdown_body="- perfective\n- imperfective",
        )
    )
    assert payload["ok"] is True
    assert payload["mime"] == "text/markdown"
    assert payload["output_kind"] == "markdown_report"
    assert "# Aspect cheatsheet" in payload["artifact"]
    assert "perfective" in payload["artifact"]


def test_html_report_default_template():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="html_report",
            title="Aspect",
            markdown_body="**Polish** aspect basics.",
        )
    )
    assert payload["ok"] is True
    assert payload["mime"] == "text/html"
    assert payload["template_name"] == "default"
    assert "<!DOCTYPE html>" in payload["artifact"]
    assert "<strong>Polish</strong>" in payload["artifact"]


def test_html_report_stakeholder_brief_template():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="html_report",
            title="Q1 review",
            markdown_body="| col | val |\n| --- | --- |\n| a | 1 |\n",
            template_name="stakeholder_brief",
        )
    )
    assert payload["ok"] is True
    assert payload["template_name"] == "stakeholder_brief"
    assert "Stakeholder brief" in payload["artifact"]
    assert "<table>" in payload["artifact"]


def test_code_snippet_branch():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="code_snippet",
            title="hello.py",
            markdown_body="print('hi')",
            programming_language="python",
        )
    )
    assert payload["ok"] is True
    assert payload["programming_language"] == "python"
    assert "```python" in payload["artifact"]


def test_code_snippet_without_language_returns_error():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="code_snippet",
            title="hello",
            markdown_body="print('hi')",
        )
    )
    assert payload["ok"] is False
    assert "canvas_validation" in payload["error"]


def test_unknown_output_kind_returns_error():
    tool = make_canvas_delivery_tool()
    payload = json.loads(
        tool(
            output_kind="pdf_report",
            title="x",
            markdown_body="y",
        )
    )
    assert payload["ok"] is False
