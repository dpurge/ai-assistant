from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.canvas.models import CanvasProduceInput


def test_markdown_report_valid():
    payload = CanvasProduceInput(
        output_kind="markdown_report",
        title="Aspect cheatsheet",
        markdown_body="- perfective\n- imperfective\n",
    )
    assert payload.output_kind == "markdown_report"
    assert payload.template_name == "default"


def test_code_snippet_requires_language():
    with pytest.raises(ValidationError, match="programming_language"):
        CanvasProduceInput(
            output_kind="code_snippet",
            title="example",
            markdown_body="print('hi')",
        )


def test_code_snippet_with_language_is_valid():
    payload = CanvasProduceInput(
        output_kind="code_snippet",
        title="hello",
        markdown_body="print('hi')",
        programming_language="python",
    )
    assert payload.programming_language == "python"


def test_whitespace_is_stripped():
    payload = CanvasProduceInput(
        output_kind="  markdown_report  ",
        title="  My title  ",
        markdown_body="  body  ",
    )
    assert payload.output_kind == "markdown_report"
    assert payload.title == "My title"
    assert payload.markdown_body == "body"


def test_template_name_defaults_to_default_when_blank():
    payload = CanvasProduceInput(
        output_kind="html_report",
        title="x",
        markdown_body="y",
        template_name="",
    )
    assert payload.template_name == "default"


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        CanvasProduceInput(
            output_kind="markdown_report",
            title="x",
            markdown_body="y",
            mystery_field="nope",
        )


def test_unknown_output_kind_rejected():
    with pytest.raises(ValidationError):
        CanvasProduceInput(
            output_kind="pdf_report",
            title="x",
            markdown_body="y",
        )


def test_unknown_template_rejected():
    with pytest.raises(ValidationError):
        CanvasProduceInput(
            output_kind="html_report",
            title="x",
            markdown_body="y",
            template_name="fancy",
        )
