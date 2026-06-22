"""Graph-shape invariants for the language-tutor SequentialAgent.

The pipeline order matters - downstream agents read state keys produced by
upstream ones. This test pins the order so a refactor that reshuffles the
sub-agent list will fail loudly. It also confirms the chat endpoint hides
internal sub-agent names from the streaming response.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTOR_PATH = REPO_ROOT / "src" / "app" / "agent" / "language" / "tutor.py"
MAIN_PATH = REPO_ROOT / "src" / "main.py"

EXPECTED_PIPELINE = [
    "text_writer",
    "metadata_writer",
    "text_transcription_writer",
    "text_translation_writer",
    "model_writer",
    "vocabulary_writer",
    "exercise_writer",
    "lesson_writer",
]


def _assigned_call(tree: ast.AST, name: str) -> ast.Call:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            if isinstance(node.value, ast.Call):
                return node.value
    raise AssertionError(f"Could not find assigned call for {name}")


def _keyword_list_names(call: ast.Call, keyword_name: str) -> list[str]:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        assert isinstance(keyword.value, ast.List), f"{keyword_name} is not a list"
        return [el.id for el in keyword.value.elts if isinstance(el, ast.Name)]
    raise AssertionError(f"Could not find keyword {keyword_name}")


def _keyword_constant(call: ast.Call, keyword_name: str) -> object:
    for keyword in call.keywords:
        if keyword.arg == keyword_name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    raise AssertionError(f"Could not find keyword constant {keyword_name}")


def test_lesson_pipeline_has_expected_sub_agent_order():
    tree = ast.parse(TUTOR_PATH.read_text(encoding="utf-8"))
    pipeline_call = _assigned_call(tree, "lesson_pipeline")
    assert _keyword_list_names(pipeline_call, "sub_agents") == EXPECTED_PIPELINE


def test_metadata_writer_emits_metadata_state_key():
    tree = ast.parse(TUTOR_PATH.read_text(encoding="utf-8"))
    metadata_writer_call = _assigned_call(tree, "metadata_writer")
    assert _keyword_constant(metadata_writer_call, "output_key") == "metadata"


def test_internal_writers_are_hidden_from_chat_stream():
    main_source = MAIN_PATH.read_text(encoding="utf-8")
    for name in (
        "metadata_writer",
        "text_transcription_writer",
        "text_translation_writer",
        "model_writer",
        "vocabulary_writer",
        "exercise_writer",
        "lesson_writer",
        "text_writer",
    ):
        assert f'"{name}"' in main_source, f"main.py should hide {name} from chat stream"
