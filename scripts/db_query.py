"""
db_query.py - 通过 MySQL 协议读取 Doris / MySQL / TiDB 的命令行查询助手

支持 DB_TYPE:
  - mysql / doris / tidb  → pymysql 驱动
  - (未来) postgres        → psycopg2 驱动

配置:
  - 从项目根目录 .env 读取连接信息 (DB_TYPE/DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_DATABASE)
  - 项目根目录 = 本脚本所在目录的上一级 (自动推导)

用法:
  python db_query.py --sql "SELECT ..."
  python db_query.py --table <table> [--database <db>] [--limit N]
  python db_query.py --file path/to/query.sql
  python db_query.py --list-tables --database <db>
  python db_query.py --describe <table>
  python db_query.py --sql "..." --format csv|json|tab
"""

import argparse
import csv
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


# ---------------------------------------------------------------------------
# 驱动注册表: DB_TYPE → 实际的 Python 驱动模块
# 未来加 postgres 时, 只需在这里加一行, 并在 connect() 加对应分支
# ---------------------------------------------------------------------------
DRIVER_MAP = {
    "mysql": "pymysql",
    "doris": "pymysql",
    "tidb": "pymysql",
    # "postgres": "psycopg2",  # 预留
}


def load_env(path=ENV_PATH):
    """读取 .env 文件为 dict. 支持注释行和空行."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"找不到 .env: {path}\n"
            f"请在项目根目录放置 .env 并写入 DB_TYPE/DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_DATABASE"
        )
    cfg = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def connect(cfg, database=None):
    """根据 .env 配置连接数据库. database 参数可覆盖默认库.

    目前 mysql/doris/tidb 都走 pymysql (它们都说 MySQL 协议).
    未来要支持 postgres 等其他协议时, 在这里加分支即可.
    """
    db_type = (cfg.get("DB_TYPE") or "mysql").lower()
    driver = DRIVER_MAP.get(db_type)
    if driver is None:
        raise ValueError(
            f"不支持的 DB_TYPE: {db_type}\n"
            f"目前支持: {', '.join(DRIVER_MAP.keys())}"
        )

    # 统一用 pymysql (mysql/doris/tidb 协议兼容)
    if driver == "pymysql":
        import pymysql
        return pymysql.connect(
            host=cfg.get("DB_HOST", "127.0.0.1"),
            port=int(cfg.get("DB_PORT", "3306")),
            user=cfg.get("DB_USER", "root"),
            password=cfg.get("DB_PASSWORD", ""),
            database=database or cfg.get("DB_DATABASE"),
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=300,
        )

    # 预留: 其他驱动的分支写在这里
    raise NotImplementedError(f"driver {driver} 未实现")


# ---------------------------------------------------------------------------
# SQL 构造
# ---------------------------------------------------------------------------

def build_sql(args):
    """根据命令行参数返回 (sql, database_override)."""
    if args.sql:
        return args.sql, None

    if args.file:
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"找不到 SQL 文件: {args.file}")
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read(), None

    if args.list_tables:
        db = args.database or "information_schema"
        return "SHOW TABLES", db

    if args.describe:
        return f"DESCRIBE {args.describe}", args.database

    if args.table:
        limit_clause = f"LIMIT {args.limit}" if args.limit else ""
        return f"SELECT * FROM {args.table} {limit_clause}".strip(), args.database

    raise ValueError("没有可执行的 SQL (用 --sql/--file/--table/--list-tables/--describe 之一)")


# ---------------------------------------------------------------------------
# 执行 + 输出
# ---------------------------------------------------------------------------

def run_and_print(cur, sql, fmt="tab", limit=None, headers=True):
    """执行 SQL, 按 fmt 格式打印到 stdout."""
    cur.execute(sql)
    rows = cur.fetchall()
    col_names = [d[0] for d in cur.description] if cur.description else []

    if limit is not None:
        rows = rows[:limit]

    if not col_names:
        print(f"-- affected rows: {cur.rowcount}")
        return

    if fmt == "json":
        payload = [dict(zip(col_names, r)) for r in rows]
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print(f"-- ({len(rows)} rows)", file=sys.stderr)

    elif fmt == "csv":
        w = csv.writer(sys.stdout)
        if headers:
            w.writerow(col_names)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
        print(f"-- ({len(rows)} rows)", file=sys.stderr)

    else:  # tab
        if headers:
            print("\t".join(col_names))
        for r in rows:
            print("\t".join("" if v is None else str(v) for v in r))
        print(f"-- ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="MySQL 协议 (Doris/MySQL/TiDB) 命令行查询助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sql", help="直接执行 SQL")
    g.add_argument("--file", help="从 .sql 文件读 SQL 执行")
    g.add_argument("--table", help="快速读整张表 (可带库前缀, 如 ods.xxx)")
    g.add_argument("--list-tables", action="store_true", help="列出某个库的所有表")
    g.add_argument("--describe", help="查看表结构 (DESCRIBE <table>)")

    ap.add_argument("--database", help="覆盖 .env 默认库 (配合 --table/--list-tables/--describe)")
    ap.add_argument("--format", choices=["tab", "csv", "json"], default="tab",
                    help="输出格式, 默认 tab")
    ap.add_argument("--limit", type=int, default=None, help="限制输出行数")
    ap.add_argument("--no-headers", action="store_true", help="不打印表头 (tab/csv)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    cfg = load_env()
    if not cfg.get("DB_PASSWORD"):
        sys.stderr.write("-- 提示: .env 中 DB_PASSWORD 为空\n")

    sql, db_override = build_sql(args)
    conn = connect(cfg, database=db_override)
    try:
        cur = conn.cursor()
        run_and_print(cur, sql, args.format, args.limit, not args.no_headers)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
