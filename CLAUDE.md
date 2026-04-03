# Hikvision Doorbell MQTT Bridge

## Project Overview

Python FastAPI application bridging a Hikvision video doorbell (ISAPI) to Home Assistant
via MQTT. Publishes MQTT discovery for lock and button entities, polls device/call status,
and executes door relay commands.

## Development

- **Python**: managed by mise (`mise exec --` for all mise-managed commands)
- **Dependencies**: Poetry (`mise exec -- poetry install`)
- **Run locally**: `mise exec -- poetry run python -m hikvision_doorbell.main`
- **Tests**: `mise exec -- poetry run coverage run -m pytest && mise exec -- poetry run coverage report -m --fail-under=80`
- **Lint**: `mise exec -- poetry run pre-commit run --all-files`
- **Pre-commit**: always run `pre-commit run --all-files` before committing

## Rules

- Always commit using semantic/conventional commits: `type: short imperative description`
- Commit messages must be concise — focus on "why", not "what"
- Always use `mise exec --` prefix for commands managed by mise (python, poetry, uv)
- When adding new features, always extend tests to cover the new functionality
- Coverage must stay ≥80% (enforced by pre-commit and CI)
- Follow existing code patterns: async-first, Pydantic models, httpx for HTTP
- Ruff for linting/formatting, line length 120, target Python 3.11+

## Architecture

- `hikvision_doorbell/app.py` — FastAPI app with lifespan context manager
- `hikvision_doorbell/main.py` — uvicorn entry point
- `hikvision_doorbell/settings.py` — Pydantic settings from env vars
- `hikvision_doorbell/helpers.py` — retry decorators, rate-limited logging
- `hikvision_doorbell/workers/doorbell.py` — main Doorbell worker (4 background tasks)
- `hikvision_doorbell/models/` — Hikvision and MQTT Pydantic models
- `tests/` — pytest test suite

## CI/CD

- GitHub Actions: build.yaml (test + build), daily-release.yml (auto-tag + release),
  release.yaml (container + chart release), merge.yaml (auto-merge renovate PRs)
- Container registry: Harbor (harbor.szymonrichert.pl)
- Helm chart under `chart/hikvision-doorbell/`
