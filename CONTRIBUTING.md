# Contributing

Thanks for helping improve the PopNow Python SDK.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Tests use [respx](https://lundberg.github.io/respx/) to mock HTTP; they never call the live API and need no API key.

## Guidelines

- Keep the runtime dependency list to `httpx` only.
- Support Python 3.9 to 3.13 (`from __future__ import annotations`, `typing.Optional`, no `match`).
- Follow the API contract in the [OpenAPI spec](https://popnow.ai/docs/openapi.yaml); do not add endpoints or fields that are not documented.
- Every new method needs a sync and an async version and a mocked test.
- Write code, comments, docs and commit messages in English.
- Never commit API keys, webhook secrets or real task output links.

## Pull requests

1. Fork the repository and create a branch.
2. Add or update tests and run `pytest`.
3. Describe the change and link any related issue.
