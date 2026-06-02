from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from .tools import (
    TOOL_CALL_ERROR_MESSAGE_KEY,
    TOOL_CALL_FAILED_KEY,
)


def clear_tool_error(callback_context: CallbackContext):
    callback_context.state[TOOL_CALL_FAILED_KEY] = False
    callback_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] = ""
    return None


def skip_if_tool_failed(callback_context: CallbackContext):
    if not callback_context.state.get(TOOL_CALL_FAILED_KEY):
        return None

    return types.Content(role="model", parts=[types.Part(text="")])


def return_tool_error(callback_context: CallbackContext):
    if not callback_context.state.get(TOOL_CALL_FAILED_KEY):
        return None

    message = callback_context.state.get(TOOL_CALL_ERROR_MESSAGE_KEY) or (
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
        message = output[len(SOURCE_LANGUAGE_CLARIFICATION_PREFIX) :].strip()
        break

    if not found_clarification:
        return None
    if not message:
        message = "What is the source language of the input text?"

    callback_context.state[TOOL_CALL_FAILED_KEY] = True
    callback_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] = message
    return None
