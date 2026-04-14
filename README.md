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

## Configuration

See [docs/configuration.md](docs/configuration.md).

## Dependencies

- Python >= 3.10
- [PyYAML](https://pypi.org/project/PyYAML/) >= 6.0
- [lark-cli](https://github.com/larksuite/cli) (install separately and authenticate)
