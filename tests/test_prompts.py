import importlib.util
import re
import unittest
from pathlib import Path


PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "app" / "agent" / "prompt.py"
)
PROMPT_SPEC = importlib.util.spec_from_file_location("agent_prompts", PROMPT_PATH)
prompts = importlib.util.module_from_spec(PROMPT_SPEC)
assert PROMPT_SPEC.loader is not None
PROMPT_SPEC.loader.exec_module(prompts)

STATE_PLACEHOLDERS = {
    "exercise_writer_output",
    "language_metadata_output",
    "model_writer_output",
    "text_transcription_output",
    "text_translation_output",
    "text_writer_output",
    "vocabulary_writer_output",
}


def _is_valid_state_name(name):
    parts = name.split(":")
    if len(parts) == 1:
        return name.isidentifier()
    if len(parts) == 2:
        return parts[0] in {"app", "user", "temp"} and parts[1].isidentifier()
    return False


class PromptTemplateTest(unittest.TestCase):
    def test_prompt_templates_do_not_require_unknown_state_keys(self):
        unknown_placeholders = []

        for prompt_name, prompt_text in vars(prompts).items():
            if not prompt_name.isupper() or not isinstance(prompt_text, str):
                continue

            for match in re.finditer(r"{+[^{}]*}+", prompt_text):
                placeholder = match.group().lstrip("{").rstrip("}").strip()
                placeholder = placeholder.removesuffix("?")
                if (
                    _is_valid_state_name(placeholder)
                    and placeholder not in STATE_PLACEHOLDERS
                ):
                    unknown_placeholders.append(f"{prompt_name}: {match.group()}")

        self.assertEqual(unknown_placeholders, [])

    def test_vocabulary_prompt_keeps_grammar_markers_source_language_only(self):
        vocabulary_prompt = " ".join(
            prompts.LANGUAGE_VOCABULARY_WRITER.split()
        )

        self.assertIn(
            "Grammar markers must describe the PHRASE in the source language",
            vocabulary_prompt,
        )
        self.assertIn(
            "Do not copy gender, number, or part-of-speech information",
            vocabulary_prompt,
        )
        self.assertIn(
            "English nouns can use `{N sg}` or `{N pl}`",
            vocabulary_prompt,
        )

    def test_lesson_formatter_prompt_requires_extractable_tags(self):
        formatter_prompt = prompts.LANGUAGE_LESSON_FORMATTER

        self.assertIn(
            '<vocabulary lang="cmn" script="hans">...</vocabulary>',
            formatter_prompt,
        )
        self.assertIn(
            '<models lang="cmn" script="hans">...</models>',
            formatter_prompt,
        )
        self.assertIn(
            '<text lang="cmn" script="hans">...</text>',
            formatter_prompt,
        )
        self.assertIn(
            '<transcription lang="cmn" script="hans" '
            'system="Hanyu Pinyin">...</transcription>',
            formatter_prompt,
        )
        self.assertIn(
            '<translation lang="pol" script="latn">...</translation>',
            formatter_prompt,
        )
        self.assertIn(
            '<exercise lang="cmn" script="hans">...</exercise>',
            formatter_prompt,
        )

        self.assertIn(
            "Put no text outside these top-level tags",
            formatter_prompt,
        )
        self.assertIn(
            "Skip the entire `<transcription>...</transcription>` block",
            formatter_prompt,
        )

    def test_lesson_formatter_prompt_requires_one_tag_per_exercise(self):
        formatter_prompt = " ".join(
            prompts.LANGUAGE_LESSON_FORMATTER.split()
        )

        self.assertIn(
            "Wrap each individual exercise in a separate "
            "`<exercise>...</exercise>` element",
            formatter_prompt,
        )
        self.assertIn(
            "Do not group multiple exercises inside one `<exercise>` block",
            formatter_prompt,
        )
        self.assertIn(
            "must contain only that exercise's instructions and body",
            formatter_prompt,
        )
        self.assertIn(
            "Do not add introductory comments, closing comments, summaries",
            formatter_prompt,
        )

    def test_exercise_writer_prompt_avoids_headers_and_comments(self):
        exercise_prompt = " ".join(prompts.LANGUAGE_EXERCISE_WRITER.split())

        self.assertIn("Return only exercise content", exercise_prompt)
        self.assertIn("Do not add introductory comments", exercise_prompt)
        self.assertIn(
            "Each exercise should contain only its instructions and body",
            exercise_prompt,
        )

    def test_text_writer_preserves_detected_source_language(self):
        text_writer_prompt = " ".join(prompts.LANGUAGE_TEXT_WRITER.split())

        self.assertIn(
            "The source language is the language of the fetched web page",
            text_writer_prompt,
        )
        self.assertIn(
            "Write the adapted lesson text in the same source language "
            "and script",
            text_writer_prompt,
        )
        self.assertIn(
            "Do not translate the lesson text into English",
            text_writer_prompt,
        )
        self.assertIn(
            "SOURCE_LANGUAGE_CLARIFICATION_NEEDED:",
            text_writer_prompt,
        )

    def test_downstream_prompts_do_not_use_english_as_bridge_language(self):
        translation_prompt = " ".join(
            prompts.LANGUAGE_TEXT_TRANSLATION.split()
        )
        model_prompt = " ".join(prompts.LANGUAGE_MODEL_WRITER.split())
        vocabulary_prompt = " ".join(
            prompts.LANGUAGE_VOCABULARY_WRITER.split()
        )
        exercise_prompt = " ".join(prompts.LANGUAGE_EXERCISE_WRITER.split())
        formatter_prompt = " ".join(
            prompts.LANGUAGE_LESSON_FORMATTER.split()
        )

        self.assertIn("Do not translate via English", translation_prompt)
        self.assertIn(
            'Do not output English phrases unless the metadata language_code '
            'is "eng"',
            model_prompt,
        )
        self.assertIn(
            'Do not output English vocabulary items unless the metadata '
            'language_code is "eng"',
            vocabulary_prompt,
        )
        self.assertIn("Write exercise instructions in Polish", exercise_prompt)
        self.assertIn("Do not use English in exercises", exercise_prompt)
        self.assertIn(
            'Do not introduce English unless language_code is "eng"',
            formatter_prompt,
        )

    def test_metadata_prompt_requires_iso_codes_and_transcription_systems(self):
        metadata_prompt = " ".join(prompts.LANGUAGE_METADATA_WRITER.split())

        self.assertIn("ISO 639-3 language code in lowercase", metadata_prompt)
        self.assertIn("ISO 15924 script code in lowercase", metadata_prompt)
        self.assertIn('"language_code"', metadata_prompt)
        self.assertIn('"script_code"', metadata_prompt)
        self.assertIn('"transcription_system"', metadata_prompt)
        self.assertIn('Use "cmn" for Mandarin Chinese', metadata_prompt)
        self.assertIn('Use "ind" for Indonesian', metadata_prompt)
        self.assertIn('Use "arb" for Modern Standard Arabic', metadata_prompt)
        self.assertIn(
            'Set "transcription_system" to "Hanyu Pinyin" for "cmn"',
            metadata_prompt,
        )
        self.assertIn(
            'Set "transcription_system" to "DIN 31635"',
            metadata_prompt,
        )

    def test_downstream_prompts_use_language_metadata(self):
        for prompt_text in (
            prompts.LANGUAGE_TEXT_TRANSCRIPTION,
            prompts.LANGUAGE_TEXT_TRANSLATION,
            prompts.LANGUAGE_MODEL_WRITER,
            prompts.LANGUAGE_VOCABULARY_WRITER,
            prompts.LANGUAGE_EXERCISE_WRITER,
            prompts.LANGUAGE_LESSON_FORMATTER,
        ):
            self.assertIn("{language_metadata_output}", prompt_text)

        transcription_prompt = " ".join(
            prompts.LANGUAGE_TEXT_TRANSCRIPTION.split()
        )
        formatter_prompt = " ".join(
            prompts.LANGUAGE_LESSON_FORMATTER.split()
        )
        self.assertIn(
            'If language_code is "cmn", use Hanyu Pinyin',
            transcription_prompt,
        )
        self.assertIn("use DIN 31635", transcription_prompt)
        self.assertIn(
            "Every source-language tag must include `lang` and `script`",
            formatter_prompt,
        )
        self.assertIn(
            "transcription tag must also include a `system` attribute",
            formatter_prompt,
        )


if __name__ == "__main__":
    unittest.main()
