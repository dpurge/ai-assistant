# ai-assistant

A language-tutor application built on **Google ADK** (Agent Development Kit), served from **FastAPI**, talking to a local **Ollama** server. It generates structured language lessons (text, transcription, translation, vocabulary, model phrases, exercises) from a URL, a file, or pasted text — and grounds answers in a private RAG corpus the user has ingested.

This README is written as a learning document. It walks through *what* the codebase does, *how* the pieces fit together, and *why* each decision was made the way it was. Every claim points at a specific file so you can read along.

---

## Table of contents

1. [What you get](#what-you-get)
2. [Quick start](#quick-start)
3. [Architecture overview](#architecture-overview)
4. [Request flow](#request-flow)
5. [Module layout](#module-layout)
6. [Deep dives](#deep-dives)
   - [6.1 The agent system](#61-the-agent-system)
   - [6.2 Tools the agents can call](#62-tools-the-agents-can-call)
   - [6.3 The RAG corpus](#63-the-rag-corpus)
   - [6.4 Canvas — structured deliverable artifacts](#64-canvas--structured-deliverable-artifacts)
   - [6.5 Lesson output: parser + Jinja2 renderer](#65-lesson-output-parser--jinja2-renderer)
   - [6.6 Configuration: `pydantic-settings`](#66-configuration-pydantic-settings)
   - [6.7 Observability: lazy Langfuse + stdlib logging](#67-observability-lazy-langfuse--stdlib-logging)
   - [6.8 Testing approach](#68-testing-approach)
   - [6.9 Containerization](#69-containerization)
7. [Patterns worth taking away](#patterns-worth-taking-away)
8. [Extending the system](#extending-the-system)
9. [Reference](#reference)

---

## What you get

- A FastAPI app with the **ADK dev-ui** mounted at `/`, plus two custom endpoints: `POST /chat` (streaming lessons) and `POST /corpus/ingest` (add a document to the private corpus).
- An eight-stage `SequentialAgent` pipeline that turns raw text into a fully-formed lesson, each stage with its own narrowly-scoped instruction prompt.
- A FAISS-backed RAG corpus with pluggable embedding backends (Ollama for real use, a deterministic fake for tests).
- A Canvas tool that produces stakeholder-style Markdown / HTML / code-snippet artifacts validated by Pydantic + rendered through Jinja2.
- A `Settings` object (one of the most important files to read first) that centralizes every knob: model names, fetch limits, embedding backend, Langfuse credentials, corpus persistence.
- Lazy Langfuse tracing that's a complete no-op until three env vars are set — so the app stays self-contained in dev.
- 91 pytest tests, 82% coverage, ruff-clean, and a slim Dockerfile.

## Quick start

Prerequisites: Python 3.12, `uv`, and a running Ollama instance with the chat and embedding models pulled.

```bash
ollama pull gemma4:31b           # chat model (configurable)
ollama pull nomic-embed-text     # embedding model for RAG (configurable)

uv sync --extra dev --extra observability
uv run assistant
```

Open:
- `http://127.0.0.1:8000/` — ADK dev-ui (the rich agent debugger)
- `http://127.0.0.1:8000/docs` — FastAPI Swagger for `/chat` and `/corpus/ingest`

CI-only quick run with the deterministic fake embedder (no Ollama needed for the RAG tests):

```bash
EMBEDDING_USE_FAKE=true uv run pytest
```

---

## Architecture overview

Three concentric layers. Reading from the outside in:

```
┌─────────────────────────────────────────────────────────────┐
│ HTTP layer  (src/main.py)                                   │
│   • POST /chat            — stream a lesson                 │
│   • POST /corpus/ingest   — add docs to the RAG corpus      │
│   • GET  /                — ADK dev-ui                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ Agent layer  (src/app/agent/)                               │
│                                                             │
│  assistant ──► language_tutor ──► lesson_pipeline           │
│   │                                ├── text_writer          │
│   │                                ├── metadata_writer      │
│   │                                ├── text_transcription_… │
│   │                                ├── text_translation_…   │
│   │                                ├── model_writer         │
│   │                                ├── vocabulary_writer    │
│   │                                ├── exercise_writer      │
│   │                                └── lesson_writer        │
│   │                                                         │
│   └── tools: read_file / read_web_page / write_file         │
│             search_private_knowledge / produce_…canvas      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ Infrastructure (src/app/{config, knowledge, rag, canvas,    │
│                          lesson, observability,             │
│                          corpus_singleton.py})              │
│                                                             │
│   Settings · FAISS index · embedding Protocol · Langfuse    │
│   span · Jinja2 templates · structured output parsing       │
└─────────────────────────────────────────────────────────────┘
```

The **infrastructure layer** has no awareness of agents. The **agent layer** plugs into infrastructure via plain Python (tools are factories that take dependencies and return a callable). The **HTTP layer** orchestrates: pick the right runner, stream events, render the structured output. This stratification is what makes the codebase testable — each layer can be exercised without booting the layer above it.

---

## Request flow

**`POST /chat`** (the lesson-generation hot path):

```
user POST /chat
   │
   ▼
src/main.py:chat_endpoint
   │   build runner, create session, open Langfuse span (no-op if disabled)
   ▼
runner.run_async() streams Events from the agent tree
   │
   ▼
event filter splits stream by event.author:
   ├── author == "lesson_pipeline"  ──► formatter_parts  (the structured XML output)
   ├── author == one of 8 internal writers ──► hidden
   └── any other author              ──► fallback_parts
   │
   ▼
_build_response():
   if formatter_parts → parse_lesson(...) → render Jinja2 Markdown
   elif fallback_parts → return raw
   │
   ▼
StreamingResponse yields one text/plain blob, span ends, langfuse flush
```

**`POST /corpus/ingest`** (sync, much simpler):

```
user POST /corpus/ingest  { doc_id, text, chunk_chars, overlap_chars }
   │
   ▼
get_corpus(settings)            ← module-level lazy singleton
   │
   ▼
corpus.ingest_text(...)
   ├── chunk_text_basic(...)    ← character-window with overlap
   ├── embedder.embed_texts(...) ← Ollama or fake
   ├── L2-normalize rows
   └── faiss_index.add_vectors(...)
   │
   ▼
persist_if_configured(corpus)   ← writes to CORPUS_PERSIST_DIR atomically
   │
   ▼
{ "doc_id": ..., "chunks_added": N, "total_chunks": M }
```

---

## Module layout

```
src/
├── main.py                          ← FastAPI app, /chat + /corpus/ingest
├── app/
│   ├── config.py                    ← pydantic-settings Settings, get_settings()
│   ├── corpus_singleton.py          ← lazy KnowledgeCorpus shared by agent + ingest
│   ├── runner.py                    ← thin Runner subclass for /chat
│   │
│   ├── agent/                       ← all ADK agent definitions
│   │   ├── assistant.py             ← root: attaches tools, mounts language_tutor
│   │   ├── prompt.py                ← ASSISTANT instruction (top-level routing)
│   │   ├── config.py                ← WORKER_MODEL = LiteLlm(...)
│   │   ├── tools.py                 ← read_file/write_file/read_web_page + state helpers
│   │   ├── state.py                 ← typed view of ToolContext.state
│   │   ├── callback.py              ← before/after-agent callbacks
│   │   ├── model.py                 ← incidental Pydantic dtos
│   │   └── language/
│   │       ├── tutor.py             ← the SequentialAgent: 8 sub-agents
│   │       └── prompt.py            ← the 8 sub-agent instruction strings
│   │
│   ├── knowledge/                   ← RAG ingest pipeline
│   │   ├── chunking.py              ← chunk_text_basic (char-window + overlap)
│   │   ├── embeddings.py            ← EmbeddingBackend Protocol + Fake + Ollama
│   │   └── store.py                 ← KnowledgeCorpus (index + chunk dict + persistence)
│   │
│   ├── rag/
│   │   └── faiss_store.py           ← FaissFlatIndex (thread-safe L2 wrapper)
│   │
│   ├── tools/                       ← ADK function-tool factories
│   │   ├── document_search_tool.py  ← make_document_search_tool(corpus)
│   │   └── canvas_tool.py           ← make_canvas_delivery_tool()
│   │
│   ├── canvas/                      ← structured deliverable artifacts
│   │   ├── models.py                ← CanvasProduceInput (Pydantic)
│   │   ├── html_templates.py        ← template path resolver
│   │   ├── artifact_extract.py      ← parse Canvas JSON from ADK events
│   │   └── templates/{default,stakeholder_brief}.html.j2
│   │
│   ├── lesson/                      ← lesson_pipeline output → Markdown
│   │   ├── models.py                ← Pydantic Lesson sections
│   │   ├── parser.py                ← XML-tag extraction + raw fallback
│   │   ├── renderer.py              ← Jinja2 Markdown render
│   │   └── templates/lesson.md.j2
│   │
│   └── observability/
│       ├── langfuse_client.py       ← lazy Langfuse (offline-safe)
│       └── langfuse_flush.py
│
tests/                               ← pytest, autouse fixtures, 91 tests
Dockerfile / docker-compose.yml      ← slim container, no ENTRYPOINT
pyproject.toml                       ← ruff, pytest, coverage, package-data
```

A useful mental model: **packages are stable, agents are arrangements of them.** If you swap out the `language_tutor` for something else, the `knowledge/`, `rag/`, `canvas/`, `lesson/`, `observability/`, and `tools/` packages remain useful unchanged.

---

## Deep dives

### 6.1 The agent system

The agent layer is built on **Google ADK**. The framework gives you three primitives this codebase uses heavily:

- `Agent` — a single model + instruction + tools, optionally with `sub_agents`.
- `SequentialAgent` — a deterministic pipeline of sub-agents; each writes a state key, the next reads.
- `ToolContext` — passed into every tool call; carries a mutable `state` dict shared across the pipeline.

The agent tree is built once at module import in `src/app/agent/assistant.py:14`:

```python
agent = Agent(
    name="assistant",
    model=WORKER_MODEL,
    instruction=ASSISTANT,
    sub_agents=[language_tutor],
    tools=[
        make_document_search_tool(_corpus),
        make_canvas_delivery_tool(),
    ],
)
```

The `language_tutor` sub-agent (in `src/app/agent/language/tutor.py`) is itself an `Agent` that owns a `SequentialAgent` called `lesson_pipeline`. The pipeline runs eight specialized writers in order:

| # | Name | Reads (state) | Writes (output_key) | Why it's separate |
|---|------|---------------|---------------------|-------------------|
| 1 | `text_writer` | user message | `text` | Adapts source to learner level; can call `read_web_page` / `read_file` |
| 2 | `metadata_writer` | `text` | `metadata` | Detects ISO 639-3 language + ISO 15924 script + transcription system |
| 3 | `text_transcription_writer` | `metadata`, `text` | `text_transcription` | Pinyin / DIN / IPA — only when metadata says one is needed |
| 4 | `text_translation_writer` | `metadata`, `text` | `text_translation` | Always to Polish; never via English |
| 5 | `model_writer` | `metadata`, `text`, transcription | `models` | 5–10 reusable model phrases |
| 6 | `vocabulary_writer` | `metadata`, `text`, transcription | `vocabulary` | 20–30 vocab items with source-language grammar markers |
| 7 | `exercise_writer` | `metadata`, `models`, `vocabulary` | `exercises` | Polish-language instructions, source-language bodies |
| 8 | `lesson_writer` | everything | `lesson` | Wraps each section in stable XML-like tags for downstream extraction |

**Why eight specialists instead of one big prompt?** Two reasons. First, each sub-agent's instruction can be narrowly scoped, which dramatically improves model behavior on small local models. Second, the SequentialAgent gives you natural checkpoints: if the metadata writer fails, downstream agents see the failure via state and short-circuit cleanly (see `callback.py`).

**Callbacks** (`src/app/agent/callback.py`) implement the failure-propagation contract:

- `clear_tool_error` (before_agent) — wipes the failure flag before the agent runs.
- `skip_if_tool_failed` (before_agent) — returns an empty `Content` to skip the agent if a prior tool failed.
- `return_tool_error` (before_agent on the formatter) — replaces the lesson with a user-friendly error message.
- `stop_if_source_language_unclear` (after_agent) — converts the special `SOURCE_LANGUAGE_CLARIFICATION_NEEDED:` prefix into a clarification question.

The failure flag itself lives in a Pydantic-typed wrapper over `ToolContext.state` (`src/app/agent/state.py`) — `get_tool_call_status` / `mark_tool_call_failed` / `clear_tool_call_status`. Keeping these helpers in one place prevents the same two string keys from being typed at every call site.

### 6.2 Tools the agents can call

ADK auto-wraps any plain callable passed via `Agent(tools=[...])` into a `FunctionTool`. The function's signature, docstring, and parameter types become the tool schema the model sees. There are two patterns in this codebase:

**Pattern 1: stateless module-level functions.** Used by `tools.py`:

```python
async def read_web_page(url: str, tool_context: ToolContext) -> dict[str, Any]:
    """Fetches a web page and returns readable text..."""
    ...
```

The docstring matters — it's the model-facing description. Both sync and async are supported (`read_web_page` is async because `httpx.AsyncClient` is non-blocking in the FastAPI event loop; `read_file` and `write_file` stay sync because stdlib has no async file API).

**Pattern 2: factory closures over dependencies.** Used by `document_search_tool.py` and `canvas_tool.py`:

```python
def make_document_search_tool(corpus: KnowledgeCorpus):
    def search_private_knowledge(retrieval_question: str, top_k: int = 6) -> str:
        ...
    return search_private_knowledge
```

The factory binds the dependency (a `KnowledgeCorpus`, a Jinja environment) at construction time so the returned callable doesn't have to fish it out of globals. This is the cleanest way to do dependency injection with ADK function tools.

**Defensive contract.** Every tool in this codebase follows the same return-shape convention: a JSON-friendly dict (or JSON string) with an explicit success/failure marker. `read_file` returns `{"status": "success"|"error", ...}`. `document_search` returns `{"hits": [...]}` or `{"hits": [], "reason": "empty_query"}`. `canvas_tool` returns `{"ok": true|false, ...}`. This is uniform enough that downstream prompts can be written to check the marker before citing.

### 6.3 The RAG corpus

The RAG subsystem is intentionally minimal. Four files, three abstractions.

**`chunking.py` — split text into windows.** `chunk_text_basic(text, *, chunk_chars=750, overlap_chars=150)` normalizes whitespace, then slides a 750-character window forward by `(750 - 150) = 600` chars per step. The overlap matters — without it, a phrase that lands across a chunk boundary becomes unfindable. Character-windowing is naive (it doesn't respect sentence boundaries) but it's deterministic and zero-dependency.

**`embeddings.py` — the `EmbeddingBackend` Protocol.** This is the linchpin of the design:

```python
class EmbeddingBackend(Protocol):
    embedding_dim: int
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Return float32 ndarray shaped (batch, embedding_dim)."""
```

A Protocol means the consumer (`KnowledgeCorpus`) doesn't import any concrete embedder — it just types its parameter as `EmbeddingBackend` and Python's structural typing does the rest. We ship two implementations:

- `FakeEmbeddingBackend` — hashes each input string into a seeded RNG and produces a unit-norm random vector. Deterministic, offline, useless for retrieval quality but perfect for tests. Used in CI via `EMBEDDING_USE_FAKE=true`.
- `OllamaEmbeddingBackend` — POSTs `{"model": ..., "input": [...]}` to Ollama's `/api/embed` (batched). Used in production. If the response dim doesn't match `settings.embedding_dimension`, it raises with a message that names the env var and tells the user to `ollama pull <model>`.

A factory `build_embedder_from_settings(settings, *, offline=None)` picks one based on `settings.embedding_use_fake`. **The application code never branches on backend.** Adding a third backend (`sentence-transformers`, OpenAI, anything) is one class plus one branch in the factory.

**`store.py` — `KnowledgeCorpus`.** Owns the FAISS index + chunk metadata dict. The two important methods:

- `ingest_text(*, doc_id, raw_text, chunk_chars, overlap_chars)` — chunks → embeds → L2-normalizes → adds to FAISS. Returns the number of chunks added. The L2 normalization is critical: with normalized vectors, Euclidean distance becomes a monotone function of cosine similarity, which is what FAISS L2 indexes are good at.
- `search_chunks(*, query, top_k)` — embeds the query, L2-normalizes, calls FAISS, joins back to the chunk dict, returns `{"chunk_id", "document_id", "snippet", "relevance_approx", "distance_l2"}`. The `relevance_approx = 1 / (1 + distance)` is a heuristic the model can compare across hits without having to reason about raw distances.

Persistence is two files plus the FAISS binary:

```
<CORPUS_PERSIST_DIR>/
├── index.faiss        ← faiss.write_index
├── chunks.jsonl       ← one ChunkRecord per line
└── chunk_order.json   ← stored payload order (FAISS internal row index → chunk_id)
```

All three writes go through `tmp + os.replace` so a crash mid-write leaves the previous state intact.

**`corpus_singleton.py`** is the glue: `get_corpus()` is a thread-safe lazy module-level singleton built from settings. Both the agent layer (`assistant.py` at import time) and the HTTP layer (`/corpus/ingest`) get the same instance, so an ingest from one process is immediately visible to the agent without any sync layer.

**`rag/faiss_store.py` — `FaissFlatIndex`.** A small wrapper around `faiss.IndexFlatL2` with a `threading.Lock` (FAISS isn't guaranteed thread-safe under writes) and a parallel list of payloads (chunk IDs). FAISS gives back row indexes; the wrapper joins them back to payloads so callers don't have to.

### 6.4 Canvas — structured deliverable artifacts

Canvas is a general-purpose tool the agent calls **when the user explicitly asks for a deliverable**: a printable handout, a stakeholder summary, a code snippet. It's distinct from the lesson pipeline (which has its own fixed structure).

The contract is enforced by a Pydantic model (`src/app/canvas/models.py`):

```python
class CanvasProduceInput(BaseModel):
    output_kind: Literal["markdown_report", "html_report", "code_snippet"]
    title: str               # min_length=1
    markdown_body: str       # min_length=1
    programming_language: str = ""  # required when output_kind == code_snippet
    template_name: Literal["default", "stakeholder_brief"] = "default"

    model_config = {"extra": "forbid"}
```

The model has three validators:
- `_normalize_kind` / `_normalize_template` — lowercase, strip whitespace, fall back to `"default"`.
- `_strip_text` — trim title/body/lang.
- `_code_requires_language` (model-level) — enforces the cross-field "code_snippet implies non-empty programming_language" rule.

The tool itself (`src/app/tools/canvas_tool.py`) is a factory that returns a sync callable. It catches `ValidationError` and returns `{"ok": false, "error": "canvas_validation:..."}` so the agent gets a structured error it can recover from instead of an exception trace.

Rendering branches on `output_kind`:

- **`markdown_report`** — just wraps `markdown_body` with a `# Title` and a horizontal-rule footer.
- **`html_report`** — converts `markdown_body` through the `markdown` library (with `tables` and `fenced_code` extensions) and pipes the result into one of two Jinja2 shells (`default.html.j2` or `stakeholder_brief.html.j2`). The Jinja environment uses `StrictUndefined` — any unknown variable is a render-time error, not a silent empty string.
- **`code_snippet`** — emits a fenced code block with the language.

There's also `artifact_extract.py` for **future use**: it parses Canvas JSON back out of an ADK `Event` stream. Today the agent surfaces the tool's JSON response directly via `/chat`, so the extractor isn't wired into an endpoint — but the code is here for when you want a `GET /canvas/latest/{session_id}` later.

### 6.5 Lesson output: parser + Jinja2 renderer

The eighth and final sub-agent in the lesson pipeline — `lesson_writer` — is instructed to wrap each section in stable XML-like tags:

```
<vocabulary lang="cmn" script="hans">…</vocabulary>
<models lang="cmn" script="hans">…</models>
<text lang="cmn" script="hans">…</text>
<transcription lang="cmn" script="hans" system="Hanyu Pinyin">…</transcription>
<translation lang="pol" script="latn">…</translation>
<exercise lang="cmn" script="hans">…</exercise>
<exercise lang="cmn" script="hans">…</exercise>
```

The HTTP layer takes that raw output and runs it through a permissive parser (`src/app/lesson/parser.py`) → typed `Lesson` model (`src/app/lesson/models.py`) → Jinja2 Markdown template (`src/app/lesson/templates/lesson.md.j2`).

**Permissive parsing matters.** Local models sometimes drift from the format — they emit extra prose, drop attributes, omit a tag. The parser uses a regex that tolerates whitespace and missing attributes, and **if no recognizable tag is found at all**, it returns a `Lesson(raw=original_text)`. The renderer then short-circuits to the raw text instead of producing an empty page. This is the same "best-effort with fallback" discipline as the Canvas validator: never let model drift produce a silent failure.

You'll see the same parsing-and-fallback pattern in `_build_response` in `main.py:84`:

```python
if formatter_parts:
    raw = "".join(formatter_parts)
    lesson = parse_lesson(raw)
    if lesson.is_structured:
        return render_lesson_markdown(lesson)
    return raw  # ← fallback to raw text if the model lost the format
```

### 6.6 Configuration: `pydantic-settings`

`src/app/config.py` is one of the most important files. Every configurable knob lives here, in one `BaseSettings` subclass:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ollama_host: str = Field("localhost", validation_alias=AliasChoices("OLLAMA_HOST"))
    ollama_port: int = Field(11434, ge=1, le=65535, ...)
    ollama_model: str = Field("ollama_chat/gemma4:31b", ...)
    fetch_timeout_seconds: float = Field(10.0, ge=1.0, le=120.0, ...)
    max_file_text_chars: int = Field(100_000, ge=1_000, ...)
    ...
    embedding_model: str = Field("nomic-embed-text", ...)
    embedding_dimension: int = Field(768, ge=8, ...)
    corpus_persist_dir: Path | None = ...
    embedding_use_fake: bool = ...
    langfuse_host / langfuse_public_key / langfuse_secret_key: str | None
```

Why bother, instead of just `os.getenv`?

- **Validation at startup.** A typo in `OLLAMA_PORT=999999` raises a `ValidationError` immediately, not a confusing connection error later.
- **One place to look.** A new contributor reads `config.py` and sees the entire surface area of env vars.
- **`.env` autoload.** Local dev gets working defaults from a file checked into `.gitignore`; production overrides via real env vars.
- **Testable.** `get_settings()` is `lru_cache`d, with `clear_settings_cache()` to reset between tests. Tests use `monkeypatch.setenv` then `clear_settings_cache()` to compose precise scenarios.
- **Type-safe properties.** `settings.ollama_api_base` is a computed `@property` that returns `f"http://{host}:{port}"` — callers don't reconstruct it.

`AliasChoices` is what lets the same setting accept multiple env-var names (handy when shipping a library or migrating env conventions). All settings here use only one alias each, but the door is open.

### 6.7 Observability: lazy Langfuse + stdlib logging

Tracing is optional and **completely off-path when unconfigured**. Look at `src/app/observability/langfuse_client.py`:

```python
def langfuse_enabled(settings) -> bool:
    return bool(settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key)

def get_langfuse(settings=None, *, strict=False):
    cfg = settings or get_settings()
    if not _credentials_ok(cfg):
        if strict: raise LangfuseUnavailable(...)
        return None
    from langfuse import Langfuse  # ← deferred import; offline runs never load this
    return Langfuse(host=..., public_key=..., secret_key=...)
```

The `from langfuse import Langfuse` is **inside** the function so the dependency is only loaded when actually needed. Combined with marking `langfuse` as an optional extra in `pyproject.toml` (`[project.optional-dependencies] observability`), this means you can install the project without the Langfuse wheel at all if you don't want it.

Spans wrap the request-level functions, not individual model calls — that's what the ADK Runner instrumentation handles automatically via context propagation:

```python
# src/main.py:48
span = start_optional_span(name="chat_turn", input=user_message, settings=settings)
try:
    async for event in runner.run_async(...):
        ...
    if span is not None:
        try: span.update(output=output)
        finally: span.end()
finally:
    flush_langfuse(settings)
```

`start_optional_span` returns `None` when Langfuse is off; the `if span is not None` guard keeps the production path clean. `flush_langfuse` is in a `finally` because spans are buffered — without a flush at request end, traces are lost if the worker recycles.

**Plain logging** (stdlib `logging.getLogger(__name__)`) handles the rest. Every tool entry/success/error gets a log line, every endpoint logs request shape, and `main()` calls `logging.basicConfig(level=INFO, ...)`. No custom logger framework; the goal was to **make the calls observable**, not to standardize the log format.

### 6.8 Testing approach

`tests/conftest.py` has three autouse fixtures and is the file to read first:

```python
@pytest.fixture(autouse=True)
def _pytest_workdir_no_dotenv(monkeypatch, tmp_path):
    """Isolate working directory so Settings(env_file='.env') doesn't pick up dev .env."""
    wd = tmp_path / "proj"; wd.mkdir(); monkeypatch.chdir(wd)

@pytest.fixture(autouse=True)
def _neutralize_runtime_env(monkeypatch):
    """Force Langfuse off and embedding backend to Fake."""
    monkeypatch.setenv("LANGFUSE_HOST", "")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("EMBEDDING_USE_FAKE", "true")

@pytest.fixture(autouse=True)
def _clear_caches():
    from app.config import clear_settings_cache
    from app.corpus_singleton import clear_corpus_cache
    clear_settings_cache(); clear_corpus_cache(); yield
    clear_settings_cache(); clear_corpus_cache()
```

Three things to take away:

- **Working-directory isolation.** Because `Settings` autoloads `.env` from cwd, tests have to run in a directory where no `.env` exists. `tmp_path` per test gives every test its own cwd.
- **Env neutralization.** The CI shell might have `LANGFUSE_HOST` set; tests reset it. Same for forcing the fake embedder.
- **Cache reset.** `lru_cache` survives across tests by default; the autouse fixture resets it both before and after each test (the `yield` is the test body).

For the embeddings backend, the **Protocol pattern pays off in tests**: `test_embeddings_ollama_mocked.py` swaps `httpx.Client` for a fake that records the request and returns canned JSON. No real HTTP, no Ollama dependency, no flaky tests. Three test cases cover the happy path, count mismatch, and dimension mismatch.

For the FastAPI endpoint, `tests/test_corpus_ingest_endpoint.py` uses `fastapi.testclient.TestClient` with the conftest fixtures already in place — the result is a clean four-test file covering accumulation, persistence, and validation errors.

### 6.9 Containerization

The Dockerfile is short and intentional:

```dockerfile
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=on PIP_NO_CACHE_DIR=off
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir ".[observability]"
EXPOSE 8000
ENTRYPOINT []
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Two non-obvious choices:

- **`ENTRYPOINT []` (explicit empty).** Without this, `docker run image custom-cmd` appends `custom-cmd` to the entrypoint. By making the entrypoint empty and putting the default in `CMD`, you can swap commands cleanly (`docker run image python -m pytest`, etc.).
- **`pip install ".[observability]"` not `uv sync`.** `uv` is great for dev but bringing it into the runtime image just to install dependencies adds 50 MB. Plain pip is fine here.

`docker-compose.yml` is a single service that exposes 8000, reads `.env`, and connects to a host-side Ollama via `host.docker.internal`. There's a commented-out `ollama:` service stub if you want to run Ollama as a sibling container.

The `[tool.setuptools.package-data]` entry in `pyproject.toml` is critical:

```toml
[tool.setuptools.package-data]
"app.lesson" = ["templates/*.j2"]
"app.canvas" = ["templates/*.j2"]
```

Without these lines, the Jinja2 templates **don't ship with the wheel**, and the app crashes at first render with a `TemplateNotFound`. This is the single most common packaging mistake when wrapping Jinja2 templates as part of a Python package.

---

## Patterns worth taking away

Six patterns from this codebase generalize to other ADK / FastAPI / RAG projects:

1. **Stratify packages so each can be tested without the layer above.** Knowledge/RAG/Canvas/Lesson have no awareness of agents; agents have no awareness of HTTP. Each layer is unit-testable in isolation.

2. **Protocols beat base classes for backend swapping.** A `Protocol` lets concrete implementations be in different packages with no inheritance chain, no abstract-base-class boilerplate, and clean test doubles.

3. **Factories beat globals for tool dependencies.** `make_document_search_tool(corpus)` is trivial to test (just pass in a corpus); a tool that fetches the corpus from a module global is not.

4. **Defensive return shapes (`{"ok": ..., ...}`).** Tools never raise into the agent loop. The agent reads `ok` and either cites or retries — and the model can be prompted to do exactly that.

5. **Lazy optional dependencies.** Langfuse imports happen inside `get_langfuse()`, not at module top. `[project.optional-dependencies]` lets users install just what they need.

6. **`Settings` as the boundary.** Everything tunable goes through one `BaseSettings` class — env, defaults, validation, computed properties — and is `lru_cache`d at the call site. New env var → new field → done.

---

## Extending the system

### Add a new tool

1. Create a new file under `src/app/tools/` exporting a factory `make_my_tool(deps...)` that returns a sync or async callable. The callable's docstring is the tool description the model sees.
2. Make sure the return shape includes a structured success/error marker so prompts can branch on it.
3. Wire it into `src/app/agent/assistant.py` (for ad-hoc tools) or into one of the sub-agent definitions in `src/app/agent/language/tutor.py` (for pipeline-scoped tools).
4. Add a paragraph to the relevant instruction prompt (`prompt.py` or `language/prompt.py`) explaining when to call it.
5. Add a unit test that exercises the factory directly — no ADK runtime needed.

### Add a new lesson section

The eight-stage `lesson_pipeline` has a stable contract. To add (say) a "cultural notes" section:

1. Add a new instruction string to `src/app/agent/language/prompt.py`.
2. Add a new `Agent(name="cultural_notes_writer", model=WORKER_MODEL, instruction=..., output_key="cultural_notes", before_agent_callback=skip_if_tool_failed)` in `src/app/agent/language/tutor.py`.
3. Insert it in the `sub_agents=[...]` list at the correct position (state keys flow forward; a writer that consumes `{cultural_notes}` must run *after* this writer).
4. Update the `lesson_writer` prompt to wrap the new content in a new tag (e.g. `<cultural_notes lang="..." script="...">...</cultural_notes>`).
5. Add a field to `src/app/lesson/models.py` `Lesson`.
6. Parse it in `src/app/lesson/parser.py`.
7. Render it in `src/app/lesson/templates/lesson.md.j2`.
8. Add the new sub-agent name to `INTERNAL_AGENT_NAMES` in `src/main.py` so it stays hidden from the chat stream.

### Add a new Canvas template

1. Drop a new `your_template.html.j2` under `src/app/canvas/templates/`.
2. Add the name to `KNOWN_HTML_TEMPLATES` in `src/app/canvas/html_templates.py` and to the `Literal[...]` in `CanvasProduceInput.template_name`.
3. Update the docstring on `produce_structured_canvas` so the model knows to use it.

### Swap the embedding backend

Implement a new class with `embedding_dim: int` and `embed_texts(texts) -> np.ndarray` (the `EmbeddingBackend` Protocol). Add a branch in `build_embedder_from_settings()`. Add a settings field if needed. Nothing else changes.

---

## Reference

### Environment variables

All variables are optional unless noted. Defaults come from `src/app/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `localhost` | Ollama hostname |
| `OLLAMA_PORT` | `11434` | Ollama port |
| `OLLAMA_MODEL` | `ollama_chat/gemma4:31b` | LiteLLM-style model ID for the chat model |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `EMBEDDING_DIMENSION` | `768` | Vector dimension — must match the model |
| `EMBEDDING_USE_FAKE` | `false` | Force the deterministic fake backend (tests / CI) |
| `CORPUS_PERSIST_DIR` | unset | If set, the FAISS index + chunks are loaded on startup and saved after each ingest |
| `FETCH_TIMEOUT_SECONDS` | `10.0` | Timeout for `read_web_page` |
| `MAX_FILE_TEXT_CHARS` / `MAX_PAGE_TEXT_CHARS` | `100_000` | Truncation limit for tool inputs |
| `VERIFY_SSL_CERTIFICATES` | `false` | TLS verification for `read_web_page` |
| `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | unset | Enable Langfuse tracing when all three are set |

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Redirects to ADK dev-ui at `/dev-ui/` |
| `POST` | `/chat?user_message=…` | Streams a generated lesson (text/plain) |
| `POST` | `/corpus/ingest` | Adds a document to the RAG corpus |
| `GET` | `/docs` | FastAPI Swagger |
| `GET` | `/list-apps` | ADK-supplied app discovery |

### Useful commands

```bash
uv sync --extra dev --extra observability  # install everything
uv run assistant                            # run the app
uv run pytest                               # run all tests
uv run pytest --cov=src/app --cov-fail-under=70  # with coverage gate
uv run ruff check src tests                 # lint
docker build -t ai-assistant .              # build the image
docker compose up                           # bring up the stack
```

### File map (the 15 files to read in order to understand everything)

1. `src/app/config.py` — what's configurable
2. `src/main.py` — request entry points
3. `src/app/agent/assistant.py` — root agent
4. `src/app/agent/prompt.py` — root instruction
5. `src/app/agent/language/tutor.py` — the 8-stage pipeline
6. `src/app/agent/language/prompt.py` — what each stage is told
7. `src/app/agent/state.py` + `callback.py` — pipeline failure protocol
8. `src/app/agent/tools.py` — file/web tools
9. `src/app/knowledge/embeddings.py` — Protocol + backends
10. `src/app/knowledge/store.py` — `KnowledgeCorpus`
11. `src/app/tools/document_search_tool.py` — factory pattern
12. `src/app/tools/canvas_tool.py` — Pydantic + Jinja2 tool
13. `src/app/lesson/parser.py` + `renderer.py` — structured output
14. `src/app/observability/langfuse_client.py` — lazy optional integration
15. `tests/conftest.py` — testing patterns
