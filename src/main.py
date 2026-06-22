import logging

import uvicorn
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from google.adk.cli.fast_api import get_fast_api_app
from google.genai import types
from pydantic import BaseModel, Field

from app.agent import root_agent
from app.config import get_settings
from app.corpus_singleton import get_corpus, persist_if_configured
from app.lesson.parser import parse_lesson
from app.lesson.renderer import render_lesson_markdown
from app.observability.langfuse_client import start_optional_span
from app.observability.langfuse_flush import flush_langfuse
from app.runner import TutorRunner

logger = logging.getLogger(__name__)

app = get_fast_api_app(agents_dir="src/app", web=True)

RESPONSE_AGENT_NAME = "lesson_pipeline"
INTERNAL_AGENT_NAMES = {
    "lesson_writer",
    "text_writer",
    "metadata_writer",
    "text_transcription_writer",
    "text_translation_writer",
    "model_writer",
    "vocabulary_writer",
    "exercise_writer",
}


@app.post("/chat")
async def chat_endpoint(user_message: str):
    settings = get_settings()
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
        logger.info("/chat: session=%s message_chars=%d", session.id, len(user_message))
        span = start_optional_span(name="chat_turn", input=user_message, settings=settings)
        formatter_parts: list[str] = []
        fallback_parts: list[str] = []
        latest_public_parts: list[str] = []

        try:
            async for event in runner.run_async(
                user_id="local-user",
                session_id=session.id,
                new_message=message,
            ):
                text_parts = _event_text_parts(event)
                if not text_parts:
                    continue

                if event.author == RESPONSE_AGENT_NAME:
                    formatter_parts.extend(text_parts)
                elif event.author not in INTERNAL_AGENT_NAMES:
                    latest_public_parts = text_parts
                    if _is_final_response(event):
                        fallback_parts = text_parts

            output = _build_response(formatter_parts, fallback_parts, latest_public_parts)
            if span is not None:
                try:
                    span.update(output=output)
                finally:
                    span.end()
            if output:
                yield output
        finally:
            flush_langfuse(settings)

    return StreamingResponse(event_stream(), media_type="text/plain")


def _build_response(
    formatter_parts: list[str],
    fallback_parts: list[str],
    latest_public_parts: list[str],
) -> str:
    if formatter_parts:
        raw = "".join(formatter_parts)
        lesson = parse_lesson(raw)
        if lesson.is_structured:
            return render_lesson_markdown(lesson)
        return raw
    if fallback_parts:
        return "".join(fallback_parts)
    if latest_public_parts:
        return "".join(latest_public_parts)
    return ""


class CorpusIngestRequest(BaseModel):
    doc_id: str | None = None
    text: str = Field(..., min_length=1)
    chunk_chars: int = Field(default=750, ge=48)
    overlap_chars: int = Field(default=150, ge=0)


class CorpusIngestResponse(BaseModel):
    doc_id: str
    chunks_added: int
    total_chunks: int


@app.post("/corpus/ingest", response_model=CorpusIngestResponse)
def corpus_ingest(payload: CorpusIngestRequest) -> CorpusIngestResponse:
    settings = get_settings()
    corpus = get_corpus(settings)
    span = start_optional_span(
        name="corpus_ingest",
        input={"doc_id": payload.doc_id, "chars": len(payload.text)},
        settings=settings,
    )
    try:
        from uuid import uuid4

        doc_id = payload.doc_id or f"doc-{uuid4()}"
        try:
            added = corpus.ingest_text(
                doc_id=doc_id,
                raw_text=payload.text,
                chunk_chars=payload.chunk_chars,
                overlap_chars=payload.overlap_chars,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        persist_if_configured(corpus, settings)
        logger.info(
            "/corpus/ingest: doc_id=%s chunks_added=%d total=%d",
            doc_id,
            added,
            corpus.chunk_count,
        )
        result = CorpusIngestResponse(
            doc_id=doc_id,
            chunks_added=added,
            total_chunks=corpus.chunk_count,
        )
        if span is not None:
            try:
                span.update(output=result.model_dump())
            finally:
                span.end()
        return result
    finally:
        flush_langfuse(settings)


def _event_text_parts(event):
    if not event.content or not event.content.parts:
        return []

    return [part.text for part in event.content.parts if part.text]


def _is_final_response(event):
    is_final_response = getattr(event, "is_final_response", None)
    return callable(is_final_response) and is_final_response()


def main(host="127.0.0.1", port=8000, reload=True):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run("main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
