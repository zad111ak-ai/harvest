# Contributing to Harvest

Thanks for your interest in contributing!

## Quick Start

```bash
git clone https://github.com/zad111ak-ai/harvest.git
cd harvest
pip install -e ".[all]"
pip install pytest ruff pre-commit
pre-commit install
```

## Development Workflow

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Run linter: `ruff check harvest/ && ruff format --check harvest/`
6. Commit with a clear message
7. Open a PR

## Code Style

- Python 3.10+ (we test on 3.10–3.13)
- Ruff for linting and formatting (run `ruff format harvest/` before committing)
- Type hints on all public functions
- Docstrings on all public classes and methods

## Testing

- All tests must pass before merging
- Add tests for new features
- Run: `python -m pytest tests/ -v`

## Reporting Bugs

Run `harvest doctor` and include the output in your bug report.

## Feature Requests

Open an issue with the `enhancement` label. Describe the use case, not just the feature.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
