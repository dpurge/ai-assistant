"""Extract Canvas JSON payloads from ADK session events (function responses).

Ported but not currently wired into ``/chat``. Available for a future
``GET /canvas/latest`` endpoint or for downstream Streamlit/UI consumers that
need to materialize artifacts back from event streams.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from google.adk.events.event import Event

CANVAS_TOOL_NAME = "produce_structured_canvas"


def _is_canvas_result_dict(candidate: Mapping[str, Any]) -> bool:
    return isinstance(candidate.get("ok"), bool)


def _unwrap_mapped_tool_response(payload: Mapping[str, Any]) -> Any | None:
    for key in ("output", "result", "response"):
        if key in payload:
            return payload[key]
    return None


def coerce_canvas_payload(raw: Any) -> dict[str, Any] | None:
    """Normalize ADK ``FunctionResponse.response`` shapes into a canvas dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return _coerce_from_json_text(raw)

    if not isinstance(raw, dict):
        return None

    if _is_canvas_result_dict(raw):
        return dict(raw)

    nested = _unwrap_mapped_tool_response(raw)
    if nested is not None:
        return coerce_canvas_payload(nested)
    if len(raw) == 1:
        return coerce_canvas_payload(next(iter(raw.values())))
    return None


def _coerce_from_json_text(text: str) -> dict[str, Any] | None:
    trimmed = text.strip()
    if not trimmed:
        return None
    try:
        parsed: Any = json.loads(trimmed)
    except json.JSONDecodeError:
        return None
    return coerce_canvas_payload(parsed)


def iter_canvas_artifacts_from_events(events: Sequence[Event]) -> list[dict[str, Any]]:
    """Return Canvas tool JSON objects in session order (successful or failed)."""
    out: list[dict[str, Any]] = []
    for event in events:
        for fr in event.get_function_responses():
            if fr.name != CANVAS_TOOL_NAME:
                continue
            payload = coerce_canvas_payload(fr.response)
            if payload is not None:
                out.append(payload)
            elif isinstance(fr.response, dict) and fr.response.get("error") is not None:
                out.append(
                    {
                        "ok": False,
                        "error": str(fr.response["error"]),
                        "output_kind": "tool_error",
                    }
                )
    return out
