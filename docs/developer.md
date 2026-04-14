# 开发指南

## 环境准备

### 方案 1：venv（开发调试）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`-e` 以可编辑模式安装，修改源码后无需重新安装即可生效。

### 方案 2：pipx（推荐，隔离干净）

[pipx](https://pipx.pypa.io/) 将每个工具安装在独立的虚拟环境中，同时将命令暴露到全局 PATH，适合作为 CLI 工具使用。

```bash
# 安装 pipx（如未安装）
brew install pipx
pipx ensurepath

# 从本地源码安装
pipx install .

# 升级（修改源码后重新安装）
pipx reinstall lark-l10n
```

卸载：

```bash
pipx uninstall lark-l10n
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

项目使用 [Hatchling](https://hatch.pypa.io/) 作为构建后端。

```bash
pip install hatch
hatch build
```

产物输出到 `dist/`，包含 `.tar.gz` 源码包和 `.whl` wheel 包。

## 发布到 PyPI

```bash
pip install twine
twine upload dist/*
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
