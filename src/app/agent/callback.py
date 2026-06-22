from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from .state import (
    clear_tool_call_status,
    get_tool_call_status,
    mark_tool_call_failed,
)


def clear_tool_error(callback_context: CallbackContext):
    clear_tool_call_status(callback_context.state)
    return None


def skip_if_tool_failed(callback_context: CallbackContext):
    if not get_tool_call_status(callback_context.state).failed:
        return None
    return types.Content(role="model", parts=[types.Part(text="")])


def return_tool_error(callback_context: CallbackContext):
    status = get_tool_call_status(callback_context.state)
    if not status.failed:
        return None

    message = status.error_message or (
        "The requested tool call failed. Please provide different input and try "
        "again."
    )
    return types.Content(role="model", parts=[types.Part(text=message)])


SOURCE_LANGUAGE_CLARIFICATION_PREFIX = "SOURCE_LANGUAGE_CLARIFICATION_NEEDED:"
SOURCE_LANGUAGE_CLARIFICATION_STATE_KEYS = (
    "language_metadata_output",
    "text_writer_output",
)


def stop_if_source_language_unclear(callback_context: CallbackContext):
    message = ""
    found_clarification = False

    for state_key in SOURCE_LANGUAGE_CLARIFICATION_STATE_KEYS:
        output = callback_context.state.get(state_key, "")
        if not isinstance(output, str):
            continue

        output = output.strip()
        if not output.startswith(SOURCE_LANGUAGE_CLARIFICATION_PREFIX):
            continue

        found_clarification = True
        message = output[len(SOURCE_LANGUAGE_CLARIFICATION_PREFIX):].strip()
        break

    if not found_clarification:
        return None
    if not message:
        message = "What is the source language of the input text?"

    mark_tool_call_failed(callback_context.state, message)
    return None
