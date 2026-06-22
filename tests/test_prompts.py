"""Prompt invariants for the language-tutor pipeline.

These tests pin behavioral guarantees of the prompts that the rest of the code
relies on: the source-language-clarification protocol, the tagged structure
expected from the lesson formatter, and the no-bridge-language constraints
that keep translations honest. They guard against silent prompt rewrites that
would break the parser or the agent graph downstream.
"""

from __future__ import annotations

import re

from app.agent.language import prompt as language_prompts

VALID_PLACEHOLDERS = {
    "metadata",
    "text",
    "text_transcription",
    "text_translation",
    "models",
    "vocabulary",
    "exercises",
}


def _is_valid_state_name(name: str) -> bool:
    return name.isidentifier()


def _iter_string_constants():
    for prompt_name, prompt_text in vars(language_prompts).items():
        if not prompt_name.isupper() or not isinstance(prompt_text, str):
            continue
        yield prompt_name, prompt_text


def test_prompt_templates_only_reference_known_state_keys():
    unknown_placeholders: list[str] = []
    for prompt_name, prompt_text in _iter_string_constants():
        for match in re.finditer(r"{+[^{}]*}+", prompt_text):
            placeholder = match.group().lstrip("{").rstrip("}").strip()
            placeholder = placeholder.removesuffix("?")
            if _is_valid_state_name(placeholder) and placeholder not in VALID_PLACEHOLDERS:
                unknown_placeholders.append(f"{prompt_name}: {match.group()}")
    assert unknown_placeholders == []


def test_text_writer_emits_source_language_clarification():
    assert "SOURCE_LANGUAGE_CLARIFICATION_NEEDED:" in language_prompts.TEXT_WRITER
    assert "Do not translate the lesson text into English or Polish" in language_prompts.TEXT_WRITER


def test_metadata_writer_requires_iso_codes():
    prompt = " ".join(language_prompts.METADATA_WRITER.split())
    assert "ISO 639-3 language code in lowercase" in prompt
    assert "ISO 15924 script code in lowercase" in prompt
    assert '"language_code"' in prompt
    assert '"script_code"' in prompt
    assert '"transcription_system"' in prompt


def test_translation_prompt_avoids_english_as_bridge_language():
    prompt = " ".join(language_prompts.TEXT_TRANSLATION.split())
    assert "Do not translate via English" in prompt


def test_vocabulary_grammar_markers_are_source_language_only():
    prompt = " ".join(language_prompts.VOCABULARY_WRITER.split())
    assert "Grammar markers must describe the PHRASE in the source language" in prompt
    assert "Do not copy gender, number, or part-of-speech information" in prompt
    assert "English nouns can use `{N sg}` or `{N pl}`" in prompt


def test_exercise_writer_returns_only_content():
    prompt = " ".join(language_prompts.EXERCISE_WRITER.split())
    assert "Return only exercise content" in prompt
    assert "Write exercise instructions in Polish" in prompt


def test_lesson_formatter_emits_extractable_tags():
    formatter = language_prompts.LESSON_FORMATTER
    assert '<vocabulary lang="cmn" script="hans">...</vocabulary>' in formatter
    assert '<models lang="cmn" script="hans">...</models>' in formatter
    assert '<text lang="cmn" script="hans">...</text>' in formatter
    assert (
        '<transcription lang="cmn" script="hans" system="Hanyu Pinyin">'
        "...</transcription>" in formatter
    )
    assert '<translation lang="pol" script="latn">...</translation>' in formatter
    assert '<exercise lang="cmn" script="hans">...</exercise>' in formatter
    assert "Put no text outside these top-level tags" in formatter
    assert "Skip the entire `<transcription>...</transcription>` block" in formatter


def test_lesson_formatter_requires_one_tag_per_exercise():
    formatter = " ".join(language_prompts.LESSON_FORMATTER.split())
    assert (
        "Wrap each individual exercise in a separate `<exercise>...</exercise>` element"
        in formatter
    )
    assert "Do not group multiple exercises inside one `<exercise>` block" in formatter
