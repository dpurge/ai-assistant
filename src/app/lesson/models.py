"""Typed view of the lesson sections emitted by the ``lesson_writer`` agent.

The ``lesson_writer`` prompt instructs the model to wrap each section in stable
XML-like tags so downstream code can extract them. These Pydantic models give
that structure a name and let the parser fail loudly when something is wrong
instead of silently passing malformed prose to the user.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LessonSection(BaseModel):
    """A tagged section with its source-language metadata attributes."""

    model_config = ConfigDict(extra="ignore")

    lang: str = ""
    script: str = ""
    body: str = ""


class TranscriptionSection(LessonSection):
    system: str = ""


class Lesson(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vocabulary: LessonSection | None = None
    models: LessonSection | None = None
    text: LessonSection | None = None
    transcription: TranscriptionSection | None = None
    translation: LessonSection | None = None
    exercises: list[LessonSection] = Field(default_factory=list)
    raw: str | None = None

    @property
    def is_structured(self) -> bool:
        return self.raw is None
