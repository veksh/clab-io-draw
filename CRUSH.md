# CRUSH.md

Setup
- Python 3.11. Prefer uv. Create env and install: uv sync --group dev
- Alt (pip): python -m venv .venv && . .venv/bin/activate && pip install -e . && pip install ruff pre-commit pytest

Build/Run
- Editable install: uv pip install -e .
- CLI: uv run clab2drawio -i topo.clab.yml; uv run drawio2clab -i topo.drawio
- Docker: docker build -t clab-io-draw .

Lint/Format
- Format: uv run ruff format .
- Lint+fix: uv run ruff check . --fix
- Pre-commit: pre-commit install; pre-commit run -a

Tests
- All: uv run pytest -q
- Single file: uv run pytest -q tests/test_clab2drawio.py
- Single test: uv run pytest -q tests/test_clab2drawio.py::test_clab2drawio_combinations
- Verbose failures: uv run pytest -q -k '<expr>' --maxfail=1 -x

Code style
- Formatter: ruff-format (double quotes, 4-space indent, target-width 88; long lines tolerated up to ~120 per pylintrc)
- Imports: sorted by ruff (I); group stdlib/third-party/local; no relative imports across packages
- Types: Python 3.11. Type hints encouraged on public APIs; annotations not required (ANN ignored). Use Path for paths
- Naming: snake_case for funcs/vars, PascalCase for classes, UPPER_CASE for constants; CLI options use kebab-case; some pep8-naming checks relaxed (N803/N806 ignored)
- Errors: raise specific exceptions; in CLIs use sys.exit(nonzero) on failure; no print—use logging.getLogger(__name__) and core.logging_config.configure_logging
- Logging: RichHandler already configured; avoid logging secrets; prefer structured, actionable messages
- YAML/XML: use YAMLProcessor/defusedxml; never eval/untrusted parsing

Notes
- No Cursor/Copilot rules found in repo. If added later (.cursor/rules or .cursorrules, .github/copilot-instructions.md), mirror them here.
