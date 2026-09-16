# Developer Guide

## Environment Setup

[uv](https://docs.astral.sh/uv/) manages the virtual environment, dependency lockfile, and command execution.

```bash
# Install uv if needed
brew install uv

# Sync dependencies and create .venv
uv sync

# Run the CLI
uv run lark-l10n --help
```

During development, use `uv run` directly. Source changes take effect immediately without reinstalling:

```bash
uv run lark-l10n push --config local/config.AIBrowser.yaml
```

To install the package as a global CLI, use `uv tool`:

```bash
uv tool install .
lark-l10n --help
```

Uninstall:

```bash
uv tool uninstall lark-l10n
```

## Project Structure

```
lark_l10n/
├── __init__.py
├── main.py          # CLI entry point; parses arguments, previews plans, confirms writes, dispatches commands
├── config_loader.py # Reads and validates YAML configuration files
├── constants.py     # Constants
├── models.py        # Data models
├── feishu_api.py    # Lark Sheets read/write wrapper
├── ios_strings.py   # .strings file parser and generator
└── sync_core.py     # Core sync logic: diff and conflict handling
```

## Build

The project uses [Hatchling](https://hatch.pypa.io/) as the build backend. Building with uv is recommended:

```bash
uv build
```

Build artifacts are written to `dist/`, including the `.tar.gz` source distribution and `.whl` wheel package.

## Publish to PyPI

```bash
uv publish
```

You can also continue using twine:

```bash
uv tool run twine upload dist/*
```

The first publish requires a PyPI account and API token. Configure them in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxx
```

## Version Management

The version is maintained in the `project.version` field in `pyproject.toml` and follows [SemVer](https://semver.org/).

New release process:

1. Update `version` in `pyproject.toml`
2. Commit and create a tag: `git tag v0.x.x`
3. Build and publish

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `PyYAML>=6.0` | Parse configuration files |
| `lark-cli` | Call Lark APIs; install and authenticate separately |

`lark-cli` is not declared as a dependency in `pyproject.toml`; users must install it separately. Repository: [larksuite/cli](https://github.com/larksuite/cli).

```bash
npm install -g @larksuiteoapi/lark-cli
lark-cli auth login
```
