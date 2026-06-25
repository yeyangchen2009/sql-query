---
name: sql-query
description: 用 Python 通过 MySQL 协议（pymysql）连接 Doris / MySQL / TiDB 等数仓，读取表数据、执行任意 SQL、导出 CSV / JSON。当用户提到「读表 / 查数据 / 跑一下 SQL / 验证 ETL 结果 / 导出 CSV / 看下这张表 / 列出库里的表 / 看表结构 / DESCRIBE / SHOW TABLES」等需求时，务必使用本 skill。即使用户没明说「doris_query」或「db_query」，只要意图是「从 SQL 数仓取数据到命令行」，就触发本 skill。
---

# sql-query

通过项目里的 `0-scripts/wrapper.py` 薄壳读取 SQL 数仓数据。

这个文件是给 Claude 运行查询时看的。安装、复制模板、settings 配置等交付说明放在 `README.md`，不要在这里展开。

## 使用原则

用户要查数据时，优先用项目薄壳执行命令：

```bash
python 0-scripts/wrapper.py ...
```

如果当前项目沿用了旧入口，例如 `0-scripts/doris_query.py` 或 `0-scripts/db_query.py`，就使用项目实际存在的薄壳文件名。

不要直接调用 skill 仓库里的 `scripts/db_query.py`，除非当前项目没有薄壳且用户明确要求临时直连。项目薄壳会把当前项目 `.env` 传给共享脚本，能避免读错数据库配置。

## 先确认什么

执行查询前先快速判断三件事：

1. 当前目录是否是业务项目根目录，或者能否定位到项目根目录
2. 项目里是否存在 `0-scripts/wrapper.py`、`0-scripts/doris_query.py` 或 `0-scripts/db_query.py`
3. 查询目标是否清楚：库名、表名、字段、时间范围、输出格式

如果用户只给了表名但没说库名，优先根据上下文判断；不确定时用 `--database` 或先列库表，不要猜业务含义。

## 常用命令

### 直接执行 SQL

适合用户已经给出完整 SQL，或需要聚合校验：

```bash
python 0-scripts/wrapper.py --sql "SELECT COUNT(*) FROM ods.xxx"
```

如果 SQL 很长，优先写到临时 `.sql` 文件再用 `--file`，避免命令行引号混乱。

### 读取表样例数据

适合用户说「看下这张表」「读一下表数据」：

```bash
python 0-scripts/wrapper.py --table ods.xxx --limit 10
```

默认先加 `--limit`，不要直接读取大表全量数据。

### 指定数据库读取裸表名

适合用户只说了表名，但上下文能确定库：

```bash
python 0-scripts/wrapper.py --table xxx --database ods --limit 10
```

### 查看表结构

适合用户问字段、类型、字段是否存在，或 SQL 报 `Unknown column`：

```bash
python 0-scripts/wrapper.py --describe ods.xxx
```

### 列出库里的表

适合用户问「DWS 有哪些表」「这个库有哪些表」：

```bash
python 0-scripts/wrapper.py --list-tables --database dws
```

### 执行 SQL 文件

适合长 SQL、验证 ETL 结果、复用已有查询文件：

```bash
python 0-scripts/wrapper.py --file path/to/query.sql
```

### 导出 CSV

适合用户说「导出给业务」「生成 CSV」：

```bash
python 0-scripts/wrapper.py --sql "SELECT * FROM ads.xxx LIMIT 100" --format csv > out.csv
```

导出前确认数据量，必要时加时间条件或 `LIMIT`。

### 导出 JSON

适合后续脚本处理或需要结构化输出：

```bash
python 0-scripts/wrapper.py --sql "SELECT * FROM ads.xxx LIMIT 20" --format json > out.json
```

JSON 模式下行数提示在 stderr，重定向后的 JSON 文件应保持纯净。

## 参数速查

五种主参数互斥，只选一个：

| 参数 | 用途 |
|------|------|
| `--sql "SELECT ..."` | 直接执行 SQL |
| `--file query.sql` | 执行 SQL 文件 |
| `--table <table>` | 快速读取表数据 |
| `--list-tables` | 列出指定库的表 |
| `--describe <table>` | 查看表结构 |

辅助参数：

| 参数 | 用途 |
|------|------|
| `--database <db>` | 指定默认库或覆盖 `.env` 默认库 |
| `--format tab|csv|json` | 指定输出格式，默认 `tab` |
| `--limit N` | 限制 `--table` 返回行数 |
| `--no-headers` | tab / csv 输出时不打印表头 |

## 查询策略

### 用户要验证 ETL 结果

优先写聚合 SQL，而不是直接拉明细：

```bash
python 0-scripts/wrapper.py --sql "SELECT dataYM, COUNT(*) FROM ads.xxx GROUP BY dataYM ORDER BY dataYM"
```

如果是验证新增字段，先看表结构，再查分布：

```bash
python 0-scripts/wrapper.py --describe ads.xxx
python 0-scripts/wrapper.py --sql "SELECT year, COUNT(*) FROM ads.xxx GROUP BY year ORDER BY year"
```

### 用户要排查字段错误

遇到 `Unknown column`、字段名不确定、蛇形/驼峰不确定时，先 `--describe`：

```bash
python 0-scripts/wrapper.py --describe ods.xxx
```

不要凭记忆改字段名。

### 用户要看大表数据

先取少量样例：

```bash
python 0-scripts/wrapper.py --table dwd.xxx --limit 20
```

需要全量导出时，先提醒用户确认范围、过滤条件和输出路径。

### 用户要业务可读结果

优先输出 tab，便于在终端看。

如果用户明确要文件，用 csv：

```bash
python 0-scripts/wrapper.py --sql "SELECT ..." --format csv > result.csv
```

## 输出解读

默认 tab 输出会显示：

```text
col1    col2
v1      v2
-- (1 rows)
```

`-- (N rows)` 是脚本追加的行数提示。生成 CSV / JSON 文件给外部使用时，注意确认文件内容是否符合目标格式。

## 安全和边界

- 不要把 `.env`、数据库密码、导出的敏感数据提交到 Git
- 不要无条件执行全表导出，先确认数据量和过滤条件
- 不要执行破坏性 SQL，除非用户明确授权并确认影响范围
- 查询生产或共享库时，优先使用只读查询

## 故障排查

| 现象 | 处理 |
|------|------|
| Claude 每次问 yes | 检查项目 `.claude/settings.local.json` 是否允许实际薄壳命令，例如 `Bash(python 0-scripts/wrapper.py*)` |
| 找不到 `.env` | 确认在业务项目根目录执行，且项目根目录有 `.env` |
| 找不到 skill 脚本 | 检查薄壳里的默认路径，或设置 `SQL_QUERY_SKILL` |
| `No module named 'pymysql'` | 安装依赖：`pip install pymysql` |
| `Access denied` | 检查 `.env` 里的账号密码 |
| `Unknown column` | 先用 `--describe` 查看表结构 |

## bundled 文件

- `scripts/db_query.py`：实际查询脚本
- `templates/0-scripts/wrapper.py`：项目薄壳模板
- `templates/env.template`：项目 `.env` 模板
- `templates/.claude/settings.snippet.json`：Claude Code allow 片段
- `README.md`：安装、迁移、多项目接入说明
