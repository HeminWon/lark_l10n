# lark-l10n

Two-way sync tool between Lark Sheets and iOS `Localizable.strings`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### Export: Lark Sheets → .strings files

```bash
lark-l10n export --config path/to/config.yaml
```

### Import: .strings files → Lark Sheets

```bash
lark-l10n import --config path/to/config.yaml
```

### Sort: sort .strings files by key

```bash
lark-l10n sort --config path/to/config.yaml
```

Reads each language's `<table_name>.strings` under `ios.input_dir`, sorts all keys alphabetically, and writes back in place. Set `sync.dry_run: true` to preview without writing.

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

Extra columns in the sheet (e.g. notes) don't need to be declared — they are ignored. On `import`, only the declared `languages` columns are written; all other columns are left untouched.

## Dependencies

- Python >= 3.10
- [PyYAML](https://pypi.org/project/PyYAML/) >= 6.0
- [lark-cli](https://github.com/larksuite/cli) (install separately and authenticate)
