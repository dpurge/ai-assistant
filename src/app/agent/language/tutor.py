from google.adk.agents import Agent, SequentialAgent

from ..config import WORKER_MODEL

from ..tools import (
    read_file,
    read_web_page,
    write_file,
)

from ..callback import (
    clear_tool_error,
    skip_if_tool_failed,
    return_tool_error,
    stop_if_source_language_unclear,
)

from .prompt import (
    LANGUAGE_TUTOR,
    TEXT_WRITER,
    METADATA_WRITER,
    TEXT_TRANSCRIPTION,
    TEXT_TRANSLATION,
    MODEL_WRITER,
    VOCABULARY_WRITER,
    EXERCISE_WRITER,
    LESSON_FORMATTER,
)


text_writer = Agent(
    name="text_writer",
    model=WORKER_MODEL,
    instruction=TEXT_WRITER,
    output_key="text",
    tools=[read_web_page, read_file],
    before_agent_callback=clear_tool_error,
    after_agent_callback=stop_if_source_language_unclear,
)

metadata_writer = Agent(
    name="metadata_writer",
    model=WORKER_MODEL,
    instruction=METADATA_WRITER,
    output_key="metadata",
    before_agent_callback=skip_if_tool_failed,
    after_agent_callback=stop_if_source_language_unclear,
)

text_transcription_writer = Agent(
    name="text_transcription_writer",
    model=WORKER_MODEL,
    instruction=TEXT_TRANSCRIPTION,
    output_key="text_transcription",
    before_agent_callback=skip_if_tool_failed,
)

text_translation_writer = Agent(
    name="text_translation_writer",
    model=WORKER_MODEL,
    instruction=TEXT_TRANSLATION,
    output_key="text_translation",
    before_agent_callback=skip_if_tool_failed,
)

model_writer = Agent(
    name="model_writer",
    model=WORKER_MODEL,
    instruction=MODEL_WRITER,
    output_key="models",
    before_agent_callback=skip_if_tool_failed,
)

vocabulary_writer = Agent(
    name="vocabulary_writer",
    model=WORKER_MODEL,
    instruction=VOCABULARY_WRITER,
    output_key="vocabulary",
    before_agent_callback=skip_if_tool_failed,
)

exercise_writer = Agent(
    name="exercise_writer",
    model=WORKER_MODEL,
    instruction=EXERCISE_WRITER,
    output_key="exercises",
    before_agent_callback=skip_if_tool_failed,
)

lesson_writer = Agent(
    name="lesson_writer",
    model=WORKER_MODEL,
    instruction=LESSON_FORMATTER,
    output_key="lesson",
    tools=[write_file],
    before_agent_callback=return_tool_error,
)

lesson_pipeline = SequentialAgent(
    name="lesson_pipeline",
    description=(
        "Create a language lesson based on the provided text, write transcription, translation, models, vocabulary, and exercises."
        "Can read web pages and local files, can save lesson text to a file."
        "Requires in the input: 1) text or URL or file path to read the text from 2) learner's level."
    ),
    sub_agents=[
        text_writer,
        metadata_writer,
        text_transcription_writer,
        text_translation_writer,
        model_writer,
        vocabulary_writer,
        exercise_writer,
        lesson_writer,
    ],
)

agent = Agent(
    name="language_tutor",
    model=WORKER_MODEL,
    instruction=LANGUAGE_TUTOR,
    sub_agents=[lesson_pipeline],
)
