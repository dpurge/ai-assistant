"""Typed helpers over the ADK ``ToolContext.state`` dict.

The pipeline communicates between sub-agents through a free-form state dict.
This module gives the two failure-tracking keys a single owner so call sites in
tools and callbacks read/write through the same helpers instead of typing the
string keys at every use.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from pydantic import BaseModel

TOOL_CALL_FAILED_KEY = "tool_call_failed"
TOOL_CALL_ERROR_MESSAGE_KEY = "tool_call_error_message"


class ToolCallStatus(BaseModel):
    failed: bool = False
    error_message: str = ""


def get_tool_call_status(state: MutableMapping[str, Any]) -> ToolCallStatus:
    return ToolCallStatus(
        failed=bool(state.get(TOOL_CALL_FAILED_KEY, False)),
        error_message=str(state.get(TOOL_CALL_ERROR_MESSAGE_KEY, "") or ""),
    )


def set_tool_call_status(
    state: MutableMapping[str, Any], *, failed: bool, error_message: str = ""
) -> None:
    state[TOOL_CALL_FAILED_KEY] = failed
    state[TOOL_CALL_ERROR_MESSAGE_KEY] = error_message


def clear_tool_call_status(state: MutableMapping[str, Any]) -> None:
    set_tool_call_status(state, failed=False, error_message="")


def mark_tool_call_failed(state: MutableMapping[str, Any], message: str) -> None:
    set_tool_call_status(state, failed=True, error_message=message)
