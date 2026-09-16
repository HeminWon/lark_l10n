# lark-l10n

Two-way sync tool between Lark Sheets and iOS `Localizable.strings`.

## Installation

[uv](https://docs.astral.sh/uv/) is recommended for environment and dependency management:

```bash
uv sync
```

Then run the CLI with `uv run`:

```bash
uv run lark-l10n --help
```

## Usage

### Pull: Lark Sheets → .strings files

```bash
uv run lark-l10n pull --config path/to/config.yaml
```

### Push: .strings files → Lark Sheets

```bash
uv run lark-l10n push --config path/to/config.yaml
```

### Sort: sort .strings files by key

```bash
uv run lark-l10n sort --config path/to/config.yaml
```

Reads each language's `<table_name>.strings` under `ios.input_dir`, sorts all keys alphabetically, and writes back in place. Unchanged files are skipped.

All three commands show a summary and offer `Y` (write), `D` (details), or `N` (cancel, the default). Details of up to 20 lines appear in the terminal; longer details are saved in a temporary `.diff` file, retained after exit. Viewing details returns to the prompt. No changes means no confirmation is needed.

Use `--yes` (or `-y`) to write immediately without prompting, including in scripts:

```bash
uv run lark-l10n push --config path/to/config.yaml --yes
```

Enter, EOF, or Ctrl+C at the prompt cancels. The former `--dry-run` option has been removed; use `D` then `N` to review without writing.

## Configuration

See [docs/configuration.md](docs/configuration.md).

### Sheet Header Alignment

The `columns` config must exactly match the header row of your Lark Sheet.

Given a sheet with this header:

| ios_key | en | zh_CN | es | pt | tr | ar |
|---------|----|-------|----|----|----|----|

Use:

```yaml
columns:
  key_column: "ios_key"   # must match the key column header exactly
  languages:
    - "en"
    - "zh_CN"             # must match language column headers exactly
    - "es"
    - "pt"
    - "tr"
    - "ar"
```

If your sheet uses a different format (e.g. `zh-CN` instead of `zh_CN`), match it in both `languages` and `mapping`:

```yaml
columns:
  key_column: "key"
  languages:
    - "en"
    - "zh-CN"

mapping:
  zh-CN:                  # must match the value in languages
    - "zh-Hans.lproj"
```

Extra columns in the sheet (e.g. notes) don't need to be declared — they are ignored. On `push`, only the declared `languages` columns are written; all other columns are left untouched.

## Dependencies

- Python >= 3.10
- [PyYAML](https://pypi.org/project/PyYAML/) >= 6.0
- [lark-cli](https://github.com/larksuite/cli) (install separately and authenticate)
