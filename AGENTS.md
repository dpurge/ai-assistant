# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python 3.12 application under `src/`. Use `src/main.py` as the FastAPI and Google ADK entrypoint, `src/app/agent.py` for agent configuration, and `src/app/runner.py` for custom runner behavior. Add new application modules under `src/app/`. The repo does not currently include `tests/` or static asset directories.

## Build, Test, and Development Commands
Use `uv` for local setup and execution:

- `uv sync` installs project dependencies from `pyproject.toml`.
- `uv run python src/main.py` starts the local development server on `127.0.0.1:8000`.
- `python3 -m compileall src` performs a quick syntax check across the codebase.

If you add new tooling, document the exact command here in the same style.

## Coding Style & Naming Conventions
Follow standard Python conventions: 4-space indentation, `snake_case` for modules, functions, and variables, and `PascalCase` for classes. Keep agent definitions in `agent.py` and web or runtime wiring in `main.py` or `runner.py`. Prefer small, focused modules over large multi-purpose files.

## Testing Guidelines
There is no automated test suite yet. When adding one, place tests under `tests/` and name files `test_*.py`. For now, verify changes with `python3 -m compileall src` and a local run of the app. Any behavior change should eventually include a regression test once test infrastructure is in place.

## Commit & Pull Request Guidelines
This repository has no established commit history yet, so use short imperative commit messages such as `Add chat streaming endpoint` or `Fix runner import path`. Pull requests should include the purpose of the change, a short summary of key edits, local verification steps, and screenshots or sample API output for user-visible behavior.

## Configuration Notes
Match the repository runtime with Python `3.12` from `.python-version`. Keep imports consistent with the actual tree; for example, the current runner lives in `src/app/runner.py`.
