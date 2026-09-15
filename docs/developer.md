# 开发指南

## 环境准备

[uv](https://docs.astral.sh/uv/) 用于管理虚拟环境、依赖锁定和命令运行。

```bash
# 安装 uv（如未安装）
brew install uv

# 同步依赖并创建 .venv
uv sync

# 运行 CLI
uv run lark-l10n --help
```

开发时直接使用 `uv run`，源码改动会立即生效，无需重新安装：

```bash
uv run lark-l10n import --config local/config.AIBrowser.yaml
```

如需安装为全局 CLI，可使用 uv tool：

```bash
uv tool install .
lark-l10n --help
```

卸载：

```bash
uv tool uninstall lark-l10n
```

## 项目结构

```
lark_l10n/
├── __init__.py
├── main.py          # CLI 入口，解析参数并分发 export/import
├── config_loader.py # 读取并校验 YAML 配置文件
├── constants.py     # 常量定义
├── models.py        # 数据模型
├── feishu_api.py    # 飞书表格读写封装
├── ios_strings.py   # .strings 文件解析与生成
└── sync_core.py     # 同步核心逻辑（diff、冲突处理、dry-run）
```

## 构建

项目使用 [Hatchling](https://hatch.pypa.io/) 作为构建后端，推荐通过 uv 构建：

```bash
uv build
```

产物输出到 `dist/`，包含 `.tar.gz` 源码包和 `.whl` wheel 包。

## 发布到 PyPI

```bash
uv publish
```

也可以继续使用 twine：

```bash
uv tool run twine upload dist/*
```

首次发布需要 PyPI 账号及 API token，建议在 `~/.pypirc` 中配置：

```ini
[pypi]
username = __token__
password = pypi-xxxxxxxx
```

## 版本管理

版本号在 `pyproject.toml` 的 `project.version` 字段维护，遵循 [SemVer](https://semver.org/)。

发布新版本流程：

1. 更新 `pyproject.toml` 中的 `version`
2. 提交并打 tag：`git tag v0.x.x`
3. 执行构建与发布

## 依赖说明

| 依赖 | 用途 |
|------|------|
| `PyYAML>=6.0` | 解析配置文件 |
| `lark-cli` | 调用飞书 API（需单独安装并完成登录） |

`lark-cli` 不在 `pyproject.toml` 的依赖中声明，需用户自行安装。仓库地址：[larksuite/cli](https://github.com/larksuite/cli)。

```bash
npm install -g @larksuiteoapi/lark-cli
lark-cli auth login
```
