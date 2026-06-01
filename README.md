# AI Assistant

`ai-assistant` is a small Google ADK and FastAPI application. It defines a single assistant agent in `src/app/agent.py`, serves the ADK web UI from the root path, and exposes a custom streaming `/chat` endpoint from `src/main.py`.

## Project layout

- `src/main.py` starts the FastAPI application and mounts the ADK web UI.
- `src/app/agent.py` defines the root tutor agent.
- `src/app/runner.py` contains the custom ADK runner used by the `/chat` endpoint.

## Prerequisites

- Python `3.12`
- `uv`
- Any model credentials required by your Google ADK setup

## Install dependencies

```bash
uv sync
```

## Start the application

Run the development server from the repository root:

```bash
uv run assistant
```

The server listens on `http://127.0.0.1:8000`.

## What to open

- ADK web UI: `http://127.0.0.1:8000/`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- App list endpoint: `http://127.0.0.1:8000/list-apps`

## Notes

- `GET /` redirects to the ADK UI under `/dev-ui/`.
- The custom `POST /chat` endpoint streams text responses.
- `uv run tutor` is the preferred entrypoint; it starts the same app as `uv run python src/main.py`.
- If chat requests fail, check that the required Google ADK model credentials are available in your environment.
