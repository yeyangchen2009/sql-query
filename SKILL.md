---
name: sql-query
description: 用 Python 通过 MySQL 协议（pymysql）连接 Doris / MySQL / TiDB 等数仓，读取表数据、执行任意 SQL、导出 CSV / JSON。当用户提到「读表 / 查数据 / 跑一下 SQL / 验证 ETL 结果 / 导出 CSV / 看下这张表 / 列出库里的表 / 看表结构 / DESCRIBE / SHOW TABLES」等需求时，务必使用本 skill。即使用户没明说「doris_query」或「db_query」，只要意图是「从 SQL 数仓取数据到命令行」，就触发本 skill。
---

# sql-query

通过 MySQL 协议读 Doris / MySQL / TiDB 的命令行查询助手。

## 什么时候用

典型触发场景：

- 「这张 ODS 表今天装了多少行？」
- 「我新加的 `year` 字段，在 ADS 表里值对不对？」
- 「把这个宽表导出成 CSV 给业务看一下」
- 「DWS 里现在有哪些表？」
- 「跑一下这个 .sql 文件看看结果」
- 「看下这张表的字段结构」

## 怎么用

### 1. 安装脚本（首次）

把本 skill 的 `scripts/db_query.py` 放到项目的 `0-scripts/` 或任意约定位置。两种方式：

- **方式 A（推荐）**：在项目里放一个 5 行薄壳，调用本 skill 的脚本。这样 skill 升级时所有项目自动生效，不用逐个同步。

  ```python
  # 0-scripts/db_query.py
  import os
  import subprocess
  import sys

  PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  env = os.environ.copy()
  env.setdefault("SQL_QUERY_ENV_PATH", os.path.join(PROJECT_ROOT, ".env"))

  SKILL_SCRIPT = r"<skill-repo-path>/scripts/db_query.py"
  subprocess.run([sys.executable, SKILL_SCRIPT] + sys.argv[1:], env=env)
  ```

- **方式 B**：直接把 `db_query.py` 复制进项目，独立维护。简单但版本会发散。

### 2. 配置 `.env`

在项目根目录创建 `.env`：

```ini
# 数据库类型: mysql | doris | tidb （都用 MySQL 协议，pymysql 驱动）
DB_TYPE=doris
DB_HOST=127.0.0.1
DB_PORT=9030
DB_USER=your_user
DB_PASSWORD=your_password
DB_DATABASE=ods
```

`.env` 不进 git（加入 `.gitignore`），每个环境各自维护。

### 3. 配置 Claude Code 免确认（可选但强烈推荐）

把下面这段加进项目的 `.claude/settings.local.json` 的 `permissions.allow`，让 Claude 跑这个脚本时不再每次问 yes：

```json
"Bash(python 0-scripts/db_query.py*)",
"Bash(python D:/<project-path>/0-scripts/db_query.py*)",
"Bash(PYTHONIOENCODING=utf-8 python 0-scripts/db_query.py*)"
```

末尾的 `*` 是通配，覆盖所有 flag 组合（`--sql/--table/--file/--list-tables/--describe/--database/--format/--limit/--no-headers`）。

### 4. 跑起来

```bash
# 直接执行 SQL
python 0-scripts/db_query.py --sql "SELECT COUNT(*) FROM ods.xxx"

# 读整张表前 10 行
python 0-scripts/db_query.py --table ods.xxx --limit 10

# 读表用裸表名 + 指定库, 导出 CSV
python 0-scripts/db_query.py --table xxx --database ods --format csv > out.csv

# 列出 DWS 库所有表
python 0-scripts/db_query.py --list-tables --database dws

# 看表结构
python 0-scripts/db_query.py --describe ods.xxx

# 跑 SQL 文件, 导出 JSON
python 0-scripts/db_query.py --file path/to/query.sql --format json > out.json
```

## 五种主参数（互斥）

| 参数 | 作用 |
|------|------|
| `--sql "SELECT ..."` | 直接执行 SQL |
| `--file xxx.sql` | 执行 SQL 文件 |
| `--table <table>` | 快速读整张表（支持 `库.表` 或裸表名 + `--database`） |
| `--list-tables` | 列出某个库的所有表 |
| `--describe <table>` | 查看表结构 |

辅助参数：`--database` / `--format tab|csv|json` / `--limit N` / `--no-headers`

## 实现要点

- **驱动选择**：脚本读 `.env` 的 `DB_TYPE`，目前 `mysql/doris/tidb` 都走 `pymysql`。未来加 `postgres` 时，在 `connect()` 里加一个 `psycopg2` 分支即可。
- **配置键前缀**：统一用 `DB_`（不是 `DORIS_`），方便跨协议复用。
- **项目根推导**：`PROJECT_ROOT = 脚本所在目录的上一级`，脚本可以放在仓库任意子目录被调用。
- **JSON 模式的行数提示打到 stderr**：保证 `> file.json` 时文件纯净。
- **NULL 处理**：tab / csv 模式下 NULL 显示为空串，json 模式下为 `null`。

## 和 IDE Database Client 的关系

IDE 适合交互式探索，本 skill 适合「命令行 / 脚本化取数」：可以管道、重定向、批量校验、定时任务、Claude Code 自动调用。

## 故障排查

| 现象 | 检查 |
|------|------|
| Claude 每次问 yes | `settings.local.json` 的 allow 是否覆盖当前命令形式 |
| `FileNotFoundError: .env` | 项目根目录是否有 `.env` |
| `Access denied` | `.env` 的 `DB_USER` / `DB_PASSWORD` |
| `Unknown column` | 用 `--describe` 看表结构再核对 |
| `No module named 'pymysql'` | `pip install pymysql` |

## bundled 文件

- `scripts/db_query.py` — 主脚本
- `templates/env.template` — `.env` 模板
- `templates/settings.snippet.json` — Claude Code 权限片段
- `README.md` — 给人看的仓库说明
