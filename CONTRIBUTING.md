# Contributing to AVI-PoC

Thank you for your interest in contributing!

## How to Contribute

- Fork the repository and create your branch from `main`.
- If you’ve fixed a bug or added a feature, open a pull request with a clear description.
- Please write clear commit messages and document your code.
- For major changes, open an issue first to discuss what you would like to change.

## Code Style
- Use PEP8 for Python code.
- Add type hints where possible.
- Write or update tests for new features or bugfixes.
- Install the development dependencies (including `pre-commit`) from `requirements.dev.txt`.
- Configure git hooks by running `pre-commit install` once after cloning the repository.
- Run `pre-commit run --all-files` before opening a pull request to ensure formatting, linting, and type checks pass locally.

## Development Commands
- `make format` — applies `isort` and `black` to the `src/` and `tests/` directories.
- `make lint` — runs Ruff against the project sources and tests.
- `make type-check` — executes mypy using the shared configuration from `pyproject.toml`.
- `pre-commit run --all-files` — executes the configured Black, isort, Ruff, mypy, and smoke test hooks locally.

## Issues
- If you find a bug, please open an issue with steps to reproduce.
- For feature requests, describe your idea and possible use case.

## License
By contributing, you agree that your contributions will be licensed under the MIT License.
