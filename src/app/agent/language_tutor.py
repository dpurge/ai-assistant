from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from .config import WORKER_MODEL
from .prompt import (
    LANGUAGE_TUTOR,
    LANGUAGE_TEXT_WRITER,
    LANGUAGE_METADATA_WRITER,
    LANGUAGE_TEXT_TRANSCRIPTION,
    LANGUAGE_TEXT_TRANSLATION,
    LANGUAGE_MODEL_WRITER,
    LANGUAGE_VOCABULARY_WRITER,
    LANGUAGE_EXERCISE_WRITER,
    LANGUAGE_LESSON_FORMATTER,
)
from .tools import (
    TOOL_CALL_ERROR_MESSAGE_KEY,
    TOOL_CALL_FAILED_KEY,
    read_file,
    read_web_page,
    write_file,
)


SOURCE_LANGUAGE_CLARIFICATION_PREFIX = "SOURCE_LANGUAGE_CLARIFICATION_NEEDED:"
SOURCE_LANGUAGE_CLARIFICATION_STATE_KEYS = (
    "language_metadata_output",
    "text_writer_output",
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


text_writer = Agent(
    name="language_tutor_text_writer",
    model=WORKER_MODEL,
    instruction=LANGUAGE_TEXT_WRITER,
    output_key="text_writer_output",
    tools=[read_web_page, read_file],
    before_agent_callback=clear_tool_error,
    after_agent_callback=stop_if_source_language_unclear,
)

language_metadata_writer = Agent(
    name="language_tutor_language_metadata_writer",
    model=WORKER_MODEL,
    instruction=LANGUAGE_METADATA_WRITER,
    output_key="language_metadata_output",
    before_agent_callback=skip_if_tool_failed,
    after_agent_callback=stop_if_source_language_unclear,
)

text_transcription = Agent(
    name="language_tutor_text_transcription",
    model=WORKER_MODEL,
    instruction=LANGUAGE_TEXT_TRANSCRIPTION,
    output_key="text_transcription_output",
)

text_translation = Agent(
    name="language_tutor_text_translation",
    model=WORKER_MODEL,
    instruction=LANGUAGE_TEXT_TRANSLATION,
    output_key="text_translation_output",
)

model_writer = Agent(
    name="language_tutor_model_writer",
    model=WORKER_MODEL,
    instruction=LANGUAGE_MODEL_WRITER,
    output_key="model_writer_output",
)

vocabulary_writer = Agent(
    name="language_tutor_vocabulary_writer",
    model=WORKER_MODEL,
    instruction=LANGUAGE_VOCABULARY_WRITER,
    output_key="vocabulary_writer_output",
)

exercise_writer = Agent(
    name="language_tutor_exercise_writer",
    model=WORKER_MODEL,
    instruction=LANGUAGE_EXERCISE_WRITER,
    output_key="exercise_writer_output",
    before_agent_callback=skip_if_tool_failed,
)

lesson_formatter = Agent(
    name="language_tutor_lesson_formatter",
    model=WORKER_MODEL,
    instruction=LANGUAGE_LESSON_FORMATTER,
    output_key="lesson_formatter_output",
    tools=[write_file],
    before_agent_callback=return_tool_error,
)

text_analyzer = SequentialAgent(
    name="language_tutor_text_analyzer",
    description=(
        "Analyze the lesson text and metadata to extract transcription, "
        "translation, models, and vocabulary."
    ),
    sub_agents=[
        text_transcription,
        text_translation,
        model_writer,
        vocabulary_writer,
    ],
    before_agent_callback=skip_if_tool_failed,
)

lesson_writer = SequentialAgent(
    name="language_tutor_lesson_pipeline",
    description=(
        "Create a language lesson based on the provided text, including "
        "transcription, translation, models, vocabulary, and exercises."
    ),
    sub_agents=[
        text_writer,
        language_metadata_writer,
        text_analyzer,
        exercise_writer,
        lesson_formatter,
    ],
)

agent = Agent(
    name="language_tutor",
    model=WORKER_MODEL,
    instruction=LANGUAGE_TUTOR,
    sub_agents=[lesson_writer],
)
