# sql-query skill

> 通过 MySQL 协议读 Doris / MySQL / TiDB 的命令行查询助手，可作为 Claude Code skill 使用。

## 这是什么

一个独立的 Claude Code skill，打包了：

- `scripts/db_query.py` — 通用查询脚本（pymysql 驱动）
- `templates/env.template` — `.env` 模板
- `templates/settings.snippet.json` — Claude Code 权限片段
- `SKILL.md` — Claude 触发和说明文档

任何使用 MySQL 协议的数仓项目（Doris / MySQL / TiDB）都能复用。

## 安装到新项目（3 步）

### 1. 克隆本仓库

```bash
git clone <repo-url> ~/claude-skills/sql-query
```

或作为子模块加进项目：

```bash
git submodule add <repo-url> .claude/skills/sql-query
```

### 2. 在项目里放薄壳

在项目的 `0-scripts/db_query.py` 写一个 5 行薄壳：

```python
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = os.environ.copy()
env.setdefault("SQL_QUERY_ENV_PATH", os.path.join(PROJECT_ROOT, ".env"))

SKILL_SCRIPT = os.path.expanduser("~/claude-skills/sql-query/scripts/db_query.py")
subprocess.run([sys.executable, SKILL_SCRIPT] + sys.argv[1:], env=env)
```

这样 skill 升级时所有项目自动生效。

### 3. 配置 `.env` 和权限

```bash
# 复制 .env 模板到项目根目录
cp ~/claude-skills/sql-query/templates/env.template .env
# 编辑 .env 填入自己的连接信息
```

把 `templates/settings.snippet.json` 里的 `allow` 数组复制到项目的 `.claude/settings.local.json`，并把 `<project-path>` 替换成实际路径。

## 使用

```bash
python 0-scripts/db_query.py --sql "SELECT COUNT(*) FROM ods.xxx"
python 0-scripts/db_query.py --table ods.xxx --limit 10
python 0-scripts/db_query.py --list-tables --database dws
python 0-scripts/db_query.py --describe ods.xxx
python 0-scripts/db_query.py --file query.sql --format csv > out.csv
```

五种主参数互斥：`--sql` / `--file` / `--table` / `--list-tables` / `--describe`

辅助参数：`--database` / `--format tab|csv|json` / `--limit N` / `--no-headers`

## 依赖

```bash
pip install pymysql
```

未来支持 PostgreSQL 时再装 `psycopg2`。

## 为什么是 skill 而不是 pip 包

- skill 的核心价值是 **Claude 能自动识别「读表 / 查数据」意图并调用**，pip 包做不到
- skill 自带权限片段配置，让 Claude 免确认执行，pip 包做不到
- skill 是文件 + 文档的组合，比 pip 包更轻

## 协议支持路线

| DB_TYPE | 驱动 | 状态 |
|---------|------|------|
| mysql | pymysql | ✅ |
| doris | pymysql | ✅ |
| tidb | pymysql | ✅ |
| postgres | psycopg2 | 预留 |

加新协议只需在 `db_query.py` 的 `DRIVER_MAP` 和 `connect()` 里各加一行。

## 许可

内部使用，未指定开源协议。
