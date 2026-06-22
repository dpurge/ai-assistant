from __future__ import annotations

from app.lesson.parser import parse_lesson
from app.lesson.renderer import render_lesson_markdown

SAMPLE_LESSON = """
<vocabulary lang="cmn" script="hans">
学校 {N} [xuéxiào] = szkoła
</vocabulary>
<models lang="cmn" script="hans">
我去学校 [wǒ qù xuéxiào] = Idę do szkoły
</models>
<text lang="cmn" script="hans">
今天天气很好。
</text>
<transcription lang="cmn" script="hans" system="Hanyu Pinyin">
Jīntiān tiānqì hěn hǎo.
</transcription>
<translation lang="pol" script="latn">
Dzisiaj pogoda jest bardzo dobra.
</translation>
<exercise lang="cmn" script="hans">
Przetłumacz: szkoła
</exercise>
<exercise lang="cmn" script="hans">
Ułóż zdanie z 学校.
</exercise>
"""


def test_parse_full_lesson():
    lesson = parse_lesson(SAMPLE_LESSON)

    assert lesson.is_structured
    assert lesson.vocabulary is not None
    assert "学校" in lesson.vocabulary.body
    assert lesson.vocabulary.lang == "cmn"
    assert lesson.vocabulary.script == "hans"
    assert lesson.models is not None
    assert "wǒ qù xuéxiào" in lesson.models.body
    assert lesson.text is not None
    assert lesson.transcription is not None
    assert lesson.transcription.system == "Hanyu Pinyin"
    assert lesson.translation is not None
    assert lesson.translation.lang == "pol"
    assert len(lesson.exercises) == 2
    assert "学校" in lesson.exercises[1].body


def test_parse_lesson_falls_back_to_raw_on_malformed_input():
    raw = "Just some prose with no tags."
    lesson = parse_lesson(raw)

    assert lesson.is_structured is False
    assert lesson.raw == raw


def test_parse_lesson_skips_empty_transcription():
    text = (
        '<text lang="deu" script="latn">Guten Tag.</text>'
        '<transcription lang="deu" script="latn" system=""></transcription>'
        '<translation lang="pol" script="latn">Dzień dobry.</translation>'
    )
    lesson = parse_lesson(text)
    assert lesson.transcription is None
    assert lesson.text is not None
    assert lesson.translation is not None


def test_render_lesson_markdown_for_structured_lesson():
    lesson = parse_lesson(SAMPLE_LESSON)
    rendered = render_lesson_markdown(lesson)

    assert "## Text" in rendered
    assert "## Transcription (Hanyu Pinyin)" in rendered
    assert "## Translation" in rendered
    assert "## Vocabulary" in rendered
    assert "## Model phrases" in rendered
    assert "## Exercises" in rendered
    assert "### Exercise 1" in rendered
    assert "### Exercise 2" in rendered
    assert "Dzisiaj pogoda" in rendered


def test_render_lesson_markdown_for_unstructured_lesson_returns_raw():
    raw = "Just some prose."
    lesson = parse_lesson(raw)
    assert render_lesson_markdown(lesson) == raw


def test_render_skips_transcription_when_empty():
    text = (
        '<text lang="deu" script="latn">Guten Tag.</text>'
        '<translation lang="pol" script="latn">Dzień dobry.</translation>'
    )
    rendered = render_lesson_markdown(parse_lesson(text))
    assert "## Transcription" not in rendered
    assert "## Text" in rendered
    assert "## Translation" in rendered
