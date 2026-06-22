from __future__ import annotations

import json

from app.canvas.artifact_extract import coerce_canvas_payload


def test_coerce_returns_canvas_dict_unchanged():
    raw = {"ok": True, "mime": "text/markdown", "artifact": "# Title"}
    assert coerce_canvas_payload(raw) == raw


def test_coerce_unwraps_nested_output_key():
    nested = {"output": {"ok": False, "error": "boom"}}
    assert coerce_canvas_payload(nested) == {"ok": False, "error": "boom"}


def test_coerce_unwraps_nested_result_key():
    nested = {"result": {"ok": True, "mime": "text/html", "artifact": "<p/>"}}
    assert coerce_canvas_payload(nested) == {
        "ok": True,
        "mime": "text/html",
        "artifact": "<p/>",
    }


def test_coerce_parses_json_text():
    raw = json.dumps({"ok": True, "mime": "text/markdown", "artifact": "x"})
    assert coerce_canvas_payload(raw) == {
        "ok": True,
        "mime": "text/markdown",
        "artifact": "x",
    }


def test_coerce_returns_none_for_unparseable():
    assert coerce_canvas_payload("not-json") is None
    assert coerce_canvas_payload(None) is None
    assert coerce_canvas_payload(["a", "b"]) is None


def test_coerce_unwraps_single_value_dict():
    nested = {"function_response": {"ok": True, "artifact": "x"}}
    assert coerce_canvas_payload(nested) == {"ok": True, "artifact": "x"}
