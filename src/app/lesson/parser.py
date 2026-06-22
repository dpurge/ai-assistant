"""Parse the XML-tagged lesson output produced by ``lesson_writer``.

The model is instructed to emit ``<vocabulary>``, ``<models>``, ``<text>``,
``<transcription>``, ``<translation>``, and one ``<exercise>`` per exercise -
each with ``lang``/``script`` attributes derived from the language metadata.
This parser pulls them out with a permissive regex (whitespace-tolerant,
case-sensitive on tag names) and falls back to wrapping the raw text in a
``Lesson(raw=...)`` so the user still sees output if the model deviates.
"""

from __future__ import annotations

import re

from app.lesson.models import Lesson, LessonSection, TranscriptionSection

_ATTR_RE = re.compile(r"""([\w:-]+)\s*=\s*"([^"]*)\"""")
_TAG_PATTERN = (
    r"<{tag}\b(?P<attrs>[^>]*)>"
    r"(?P<body>.*?)"
    r"</{tag}\s*>"
)


def _iter_sections(tag: str, text: str):
    pattern = re.compile(_TAG_PATTERN.format(tag=tag), re.DOTALL)
    for match in pattern.finditer(text):
        attrs = dict(_ATTR_RE.findall(match.group("attrs") or ""))
        body = (match.group("body") or "").strip()
        yield attrs, body


def _first(tag: str, text: str) -> LessonSection | None:
    for attrs, body in _iter_sections(tag, text):
        return LessonSection(
            lang=attrs.get("lang", ""),
            script=attrs.get("script", ""),
            body=body,
        )
    return None


def _first_transcription(text: str) -> TranscriptionSection | None:
    for attrs, body in _iter_sections("transcription", text):
        if not body:
            return None
        return TranscriptionSection(
            lang=attrs.get("lang", ""),
            script=attrs.get("script", ""),
            system=attrs.get("system", ""),
            body=body,
        )
    return None


def parse_lesson(raw_text: str) -> Lesson:
    """Best-effort parse of the lesson_writer output.

    Returns a ``Lesson`` with parsed sections when at least one tag is found,
    otherwise a ``Lesson(raw=raw_text)`` that callers can fall back to rendering
    verbatim.
    """
    text = raw_text or ""

    vocabulary = _first("vocabulary", text)
    models = _first("models", text)
    body_text = _first("text", text)
    transcription = _first_transcription(text)
    translation = _first("translation", text)

    exercises: list[LessonSection] = []
    for attrs, body in _iter_sections("exercise", text):
        if not body:
            continue
        exercises.append(
            LessonSection(
                lang=attrs.get("lang", ""),
                script=attrs.get("script", ""),
                body=body,
            )
        )

    sections = (vocabulary, models, body_text, transcription, translation)
    if not any(section is not None for section in sections) and not exercises:
        return Lesson(raw=text.strip())

    return Lesson(
        vocabulary=vocabulary,
        models=models,
        text=body_text,
        transcription=transcription,
        translation=translation,
        exercises=exercises,
    )
