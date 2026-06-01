import ast
import unittest
from pathlib import Path


LANGUAGE_TUTOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "app"
    / "agent"
    / "language_tutor.py"
)
MAIN_PATH = Path(__file__).resolve().parents[1] / "src" / "main.py"


def _assigned_call(tree, name):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            if isinstance(node.value, ast.Call):
                return node.value
    raise AssertionError(f"Could not find assigned call for {name}")


def _keyword_list_names(call, keyword_name):
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        if not isinstance(keyword.value, ast.List):
            raise AssertionError(f"{keyword_name} is not a list")
        return [
            element.id
            for element in keyword.value.elts
            if isinstance(element, ast.Name)
        ]
    raise AssertionError(f"Could not find keyword {keyword_name}")


class LanguageTutorGraphTest(unittest.TestCase):
    def test_metadata_writer_runs_between_text_writer_and_analyzer(self):
        tree = ast.parse(LANGUAGE_TUTOR_PATH.read_text(encoding="utf-8"))

        lesson_writer_call = _assigned_call(tree, "lesson_writer")
        self.assertEqual(
            _keyword_list_names(lesson_writer_call, "sub_agents"),
            [
                "text_writer",
                "language_metadata_writer",
                "text_analyzer",
                "exercise_writer",
                "lesson_formatter",
            ],
        )

        metadata_writer_call = _assigned_call(tree, "language_metadata_writer")
        output_keys = [
            keyword.value.value
            for keyword in metadata_writer_call.keywords
            if keyword.arg == "output_key"
            and isinstance(keyword.value, ast.Constant)
        ]
        self.assertEqual(output_keys, ["language_metadata_output"])

    def test_metadata_writer_is_hidden_from_chat_stream(self):
        main_source = MAIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            '"language_tutor_language_metadata_writer"',
            main_source,
        )


if __name__ == "__main__":
    unittest.main()
