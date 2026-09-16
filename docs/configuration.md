# 配置文件说明

可直接复制仓库根目录的 [config.example.yaml](../config.example.yaml)，修改表格地址、工作表 ID、本地路径和语言列名后使用。模板默认关闭删除。当前没有自动生成配置的子命令。

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

push:
  mode: "upsert"        # append（仅追加新 key）| upsert（追加 + 更新）
  conflict: "local-first"  # local-first | sheet-first
  empty_overwrite: false   # 本地空值是否覆盖飞书非空值
  delete_missing: false    # true 时删除飞书中本地已不存在的 key 对应整行

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

### push

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | string | `upsert` | `append` 只追加新 key；`upsert` 同时更新已有 key |
| `conflict` | string | `local-first` | 两端都有值且不同时，`local-first` 以本地为准，`sheet-first` 保留飞书值 |
| `empty_overwrite` | bool | `false` | 本地为空时是否覆盖飞书的非空值 |
| `delete_missing` | bool | `false` | 仅限 `upsert`：删除本地所有参与同步语言均不存在的 key 对应整行 |

这组策略仅用于 `push`。旧配置请将 `sync:` 改为 `push:`，不再读取旧节；`pull` 和 `sort` 不要求提供 `push` 节。

开启删除时，本地全部参与同步的语言文件必须存在并可完整解析，且至少读到一个 key，否则停止整个 push。空翻译不会被当成 key 删除，只要任一参与同步语言仍有此 key 就会保留。飞书范围内无 key 的空行不会删除。`append` 模式不可开启删除。

删除以当前读取范围中的 key 为准，删除的是工作表整行（包含备注和未同步语言等其他列），只应用于由当前项目管理的 key 区域。摘要显示删除行数，`D` 列出 key 和原行号。确认后先备份，再更新、追加，最后从下往上删除，避免行号错位；执行失败即停止，已成功的步骤不会自动回滚。

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

## push 自动备份

确认 `Y` 或带 `--yes` 时，先把本次读取的飞书原始数据保存为 CSV，再执行任何写入。位置固定，无需新增参数或配置：

```text
~/.lark_l10n/backups/<表格 token>/<工作表 ID>/<时间戳>.csv
```

使用 UTF-8 BOM 编码，包含表头和本次读取范围内的所有列（包括未参与同步的列），保留逗号、引号和多行文本。若配置了 `feishu.range`，通常仅备份该范围；本次有删除行时自动备份整个工作表的数据，覆盖其他列；终端会显示备份路径和范围。备份仅保存读取到的单元格数据，不保存格式、合并或完整公式信息。

备份失败则停止写入；取消、无变更、`pull` 和 `sort` 不备份。文件持续保留，不自动清理。

`lark-cli sheets +csv-put` 支持从 CSV 写入现有工作表，`+workbook-import` 支持将 CSV 导入为新电子表格。恢复到原表时，应使用原读取范围的左上角作为起点；CSV 写入不会自动删除备份范围之外后来新增的行，因此不等同于整表回滚。另外，CSV 导入可能自动识别数字或公式，纯文本如前导零编号应核对类型。
