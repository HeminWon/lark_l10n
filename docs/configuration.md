# 配置文件说明

## 完整示例

```yaml
feishu:
  url: "https://your-tenant.feishu.cn/sheets/shtcnYYYYYYYYYY?sheet=XXXXXX"  # 或填 spreadsheet_token
  sheet_id: "XXXXXX"
  range: null  # 留空自动检测

ios:
  input_dir: "/path/to/project"   # push 时读取 .strings 的根目录
  output_dir: "/path/to/output"   # pull 时写出 .strings 的根目录
  table_name: "Localizable"

sync:
  mode: "upsert"        # append（仅追加新 key）| upsert（追加 + 更新）
  conflict: "local-first"  # local-first | sheet-first
  empty_overwrite: false   # 本地空值是否覆盖飞书非空值

columns:
  key_column: "ios_key"
  languages:
    - "zh_CN"
    - "en"
    - "es"
    - "pt"
    - "tr"
    - "ar"
    - "id"
    - "ms"

mapping:
  zh_CN:
    - "zh-Hans.lproj"
  pt:
    - "pt-BR.lproj"
    - "pt-PT.lproj"   # 按顺序查找，取第一个存在的
```

## 字段说明

### feishu

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | string | 飞书表格链接，与 `spreadsheet_token` 二选一 |
| `sheet_id` | string | 工作表 ID，从 URL 中的 `sheet=` 参数获取 |
| `range` | string \| null | 读取范围，留空自动检测全表 |

### ios

| 字段 | 类型 | 说明 |
|------|------|------|
| `input_dir` | string | `push` / `sort` 时读取 `.strings` 文件的项目根目录 |
| `output_dir` | string | `pull` 时写出 `.strings` 文件的目标根目录 |
| `table_name` | string | `.strings` 文件名（不含扩展名），默认 `Localizable` |

### sync

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | string | `upsert` | `append` 只追加新 key；`upsert` 同时更新已有 key |
| `conflict` | string | `local-first` | 两端都有值且不同时，`local-first` 以本地为准，`sheet-first` 保留飞书值 |
| `empty_overwrite` | bool | `false` | 本地为空时是否覆盖飞书的非空值 |

### columns

| 字段 | 类型 | 说明 |
|------|------|------|
| `key_column` | string | 飞书表格中存放 iOS key 的列名 |
| `languages` | list | 需要参与同步的语言列名列表，须与飞书表格列名一致；`push` 时仅更新这些列，不会重排远端表头 |

> `push` 在 `upsert` 模式下会保持远端已有列结构（列名与顺序）不变。即使配置中移除了某个语言（如 `zh_CN`），也不会删除或移动远端该列。

> `sort` 命令仅依赖 `ios.input_dir`、`ios.table_name`、`columns.languages`和 `mapping`，不需要飞书配置。按 key 字典序重写每个语言的单表文件，注释不保留。

### mapping

语言列名到 `.lproj` 目录的映射。未配置的语言默认使用 `{lang}.lproj`。

支持配置多个候选目录，按顺序查找，取第一个存在的：

```yaml
mapping:
  pt:
    - "pt-BR.lproj"
    - "pt-PT.lproj"
```

## 预览与执行确认

不再读取配置中的 `sync.dry_run`，旧配置可删除此字段；命令行 `--dry-run` 也已移除。

`pull`、`push`、`sort` 默认先展示摘要，再选择：

- `Y`：确认写入。
- `D`：查看完整明细。最多 20 行时直接展示，超过时写入独立的临时 `.diff` 文件并显示路径；文件退出后保留。查看后返回选择提示。
- `N`、回车、Ctrl+C 或输入结束：取消写入。

输入不区分大小写，无变更时直接结束。文件命令跳过内容未变化的文件。

使用 `--yes`（简写 `-y`）跳过确认，直接写入，适用于脚本：

```bash
uv run lark-l10n push --config path/to/config.yaml --yes
```
