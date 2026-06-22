"""Pydantic contract for ``produce_structured_canvas`` tool arguments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CanvasOutputKind = Literal["markdown_report", "html_report", "code_snippet"]
CanvasHtmlTemplateName = Literal["default", "stakeholder_brief"]


class CanvasProduceInput(BaseModel):
    """Validated payload authored by the agent before rendering."""

    output_kind: CanvasOutputKind = Field(
        ...,
        description=(
            "markdown_report - returns Markdown; "
            "html_report wraps Markdown into a Jinja HTML shell; "
            "code_snippet emits a fenced snippet."
        ),
    )
    title: str = Field(..., min_length=1, description="Displayed heading.")
    markdown_body: str = Field(
        ...,
        min_length=1,
        description="Primary narrative Markdown (bullet lists, headings, citations).",
    )
    programming_language: str = Field(
        default="",
        max_length=64,
        description="Required when output_kind == 'code_snippet'.",
    )
    template_name: CanvasHtmlTemplateName = Field(
        default="default",
        description="Jinja HTML shell when output_kind == 'html_report'.",
    )

    model_config = {"extra": "forbid"}

    @field_validator("output_kind", mode="before")
    @classmethod
    def _normalize_kind(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("template_name", mode="before")
    @classmethod
    def _normalize_template(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower() or "default"
        return value

    @field_validator(
        "title",
        "markdown_body",
        "programming_language",
        mode="before",
    )
    @classmethod
    def _strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _code_requires_language(self) -> CanvasProduceInput:
        if self.output_kind == "code_snippet" and not self.programming_language.strip():
            raise ValueError(
                "`programming_language` is required when `output_kind` is `code_snippet`."
            )
        return self
