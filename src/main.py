import uvicorn
from fastapi.responses import StreamingResponse

from google.adk.cli.fast_api import get_fast_api_app
from google.genai import types

from app.agent import root_agent
from app.runner import TutorRunner

app = get_fast_api_app(agents_dir="src/app", web=True)

LESSON_FORMATTER_AGENT_NAME = "language_tutor_lesson_formatter"
INTERNAL_LESSON_AGENT_NAMES = {
    "language_tutor_lesson_pipeline",
    "language_tutor_text_writer",
    "language_tutor_language_metadata_writer",
    "language_tutor_text_analyzer",
    "language_tutor_text_transcription",
    "language_tutor_text_translation",
    "language_tutor_model_writer",
    "language_tutor_vocabulary_writer",
    "language_tutor_exercise_writer",
}


@app.post("/chat")
async def chat_endpoint(user_message: str):
    runner = TutorRunner(agent=root_agent)
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="local-user",
    )
    message = types.Content(
        role="user",
        parts=[types.Part(text=user_message)],
    )

    async def event_stream():
        formatter_parts = []
        fallback_parts = []
        latest_public_parts = []

        async for event in runner.run_async(
            user_id="local-user",
            session_id=session.id,
            new_message=message,
        ):
            text_parts = _event_text_parts(event)
            if not text_parts:
                continue

            if event.author == LESSON_FORMATTER_AGENT_NAME:
                formatter_parts.extend(text_parts)
            elif event.author not in INTERNAL_LESSON_AGENT_NAMES:
                latest_public_parts = text_parts
                if _is_final_response(event):
                    fallback_parts = text_parts

        if formatter_parts:
            yield "".join(formatter_parts)
        elif fallback_parts:
            yield "".join(fallback_parts)
        elif latest_public_parts:
            yield "".join(latest_public_parts)

    return StreamingResponse(event_stream(), media_type="text/plain")


def _event_text_parts(event):
    if not event.content or not event.content.parts:
        return []

    return [part.text for part in event.content.parts if part.text]


def _is_final_response(event):
    is_final_response = getattr(event, "is_final_response", None)
    return callable(is_final_response) and is_final_response()


def main(host="127.0.0.1", port=8000, reload=True):
    uvicorn.run("main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
