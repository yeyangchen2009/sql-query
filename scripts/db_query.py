"""
db_query.py - 多数据库命令行查询助手 (Doris / MySQL / TiDB / SQL Server)

支持 DB_TYPE:
  - mysql / doris / tidb    → pymysql 驱动
  - sqlserver / mssql       → pymssql 驱动
  - (未来) postgres          → psycopg2 驱动

配置:
  - 默认从脚本所在 skill 目录上一级读取 .env
  - 被项目薄壳调用时, 可通过 SQL_QUERY_ENV_PATH 指向项目自己的 .env
  - 多连接: 默认连接用 DB_* 前缀, 其他连接用 <NAME>_DB_* 前缀, 通过 --conn <name> 选择

用法:
  python db_query.py --sql "SELECT ..."
  python db_query.py --conn rx --sql "SELECT ..."
  python db_query.py --list-conns
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
ENV_PATH = os.environ.get("SQL_QUERY_ENV_PATH", os.path.join(PROJECT_ROOT, ".env"))


# ---------------------------------------------------------------------------
# 驱动注册表: DB_TYPE → 实际的 Python 驱动模块
# 未来加 postgres 时, 只需在这里加一行, 并在 connect() 加对应分支
# ---------------------------------------------------------------------------
DRIVER_MAP = {
    "mysql": "pymysql",
    "doris": "pymysql",
    "tidb": "pymysql",
    "sqlserver": "pymssql",
    "mssql": "pymssql",
    # "postgres": "psycopg2",  # 预留
}

# 每种驱动的默认端口
DEFAULT_PORT = {
    "pymysql": 3306,
    "pymssql": 1433,
}

# 一个连接配置认识的字段后缀
CONN_KEYS = ("TYPE", "HOST", "PORT", "USER", "PASSWORD", "DATABASE")


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


def list_conns(cfg):
    """返回 .env 里所有连接名. 默认连接名是 'default' (DB_* 前缀)."""
    names = []
    if "DB_HOST" in cfg:
        names.append("default")
    for k in cfg:
        if k.endswith("_DB_HOST"):
            names.append(k[: -len("_DB_HOST")].lower())
    return names


def select_conn(cfg, conn=None):
    """挑出某个连接的配置, 归一化成不带前缀的 DB_* dict.

    conn 为 None / 'default' 时用 DB_* 前缀; 否则用 <CONN>_DB_* 前缀 (大小写不敏感).
    """
    prefix = "" if not conn or conn.lower() == "default" else conn.upper() + "_"
    picked = {}
    for suffix in CONN_KEYS:
        key = f"{prefix}DB_{suffix}"
        if key in cfg:
            picked[f"DB_{suffix}"] = cfg[key]

    if not picked.get("DB_HOST"):
        available = list_conns(cfg)
        raise ValueError(
            f"找不到连接配置: {conn or 'default'} (期望 .env 里有 {prefix}DB_HOST)\n"
            f"可用连接: {', '.join(available) if available else '(无)'}"
        )
    return picked


def connect(cfg, database=None, conn=None):
    """根据 .env 配置连接数据库.

    conn     : 连接名, None 表示默认连接 (DB_* 前缀)
    database : 覆盖该连接的默认库

    mysql/doris/tidb 走 pymysql (MySQL 协议); sqlserver/mssql 走 pymssql (TDS 协议).
    未来要支持 postgres 等其他协议时, 在这里加分支即可.
    """
    c = select_conn(cfg, conn)

    db_type = (c.get("DB_TYPE") or "mysql").lower()
    driver = DRIVER_MAP.get(db_type)
    if driver is None:
        raise ValueError(
            f"不支持的 DB_TYPE: {db_type}\n"
            f"目前支持: {', '.join(DRIVER_MAP.keys())}"
        )

    host = c.get("DB_HOST", "127.0.0.1")
    port = int(c.get("DB_PORT") or DEFAULT_PORT.get(driver, 3306))
    user = c.get("DB_USER", "root")
    password = c.get("DB_PASSWORD", "")
    dbname = database or c.get("DB_DATABASE")

    if driver == "pymysql":
        import pymysql
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=300,
        )

    if driver == "pymssql":
        import pymssql
        return pymssql.connect(
            server=host,
            port=port,
            user=user,
            password=password,
            database=dbname or "",
            charset="UTF-8",
            login_timeout=10,
            timeout=300,
        )

    # 预留: 其他驱动的分支写在这里
    raise NotImplementedError(f"driver {driver} 未实现")


# ---------------------------------------------------------------------------
# SQL 构造
# ---------------------------------------------------------------------------

def build_sql(args, driver="pymysql"):
    """根据命令行参数返回 (sql, database_override).

    driver 决定方言: pymysql 用 SHOW TABLES / DESCRIBE / LIMIT,
    pymssql 用 INFORMATION_SCHEMA / SELECT TOP N.
    """
    is_mssql = driver == "pymssql"

    if args.sql:
        return args.sql, None

    if args.file:
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"找不到 SQL 文件: {args.file}")
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read(), None

    if args.list_tables:
        if is_mssql:
            return (
                "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                "FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"
            ), args.database
        db = args.database or "information_schema"
        return "SHOW TABLES", db

    if args.describe:
        if is_mssql:
            # 支持 schema.table 与裸表名
            parts = args.describe.split(".")
            table = parts[-1]
            schema_filter = f" AND TABLE_SCHEMA = '{parts[-2]}'" if len(parts) > 1 else ""
            return (
                "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
                "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_NAME = '{table}'{schema_filter} ORDER BY ORDINAL_POSITION"
            ), args.database
        return f"DESCRIBE {args.describe}", args.database

    if args.table:
        if is_mssql:
            top = f"TOP {args.limit} " if args.limit else ""
            return f"SELECT {top}* FROM {args.table}", args.database
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
        description="多数据库命令行查询助手 (Doris/MySQL/TiDB/SQL Server)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sql", help="直接执行 SQL")
    g.add_argument("--file", help="从 .sql 文件读 SQL 执行")
    g.add_argument("--table", help="快速读整张表 (可带库前缀, 如 ods.xxx)")
    g.add_argument("--list-tables", action="store_true", help="列出某个库的所有表")
    g.add_argument("--describe", help="查看表结构")
    g.add_argument("--list-conns", action="store_true", help="列出 .env 里配置的所有连接名")

    ap.add_argument("--conn", help="选择连接名 (默认 default, 对应 .env 的 DB_* 前缀)")
    ap.add_argument("--database", help="覆盖连接默认库 (配合 --table/--list-tables/--describe)")
    ap.add_argument("--format", choices=["tab", "csv", "json"], default="tab",
                    help="输出格式, 默认 tab")
    ap.add_argument("--limit", type=int, default=None, help="限制输出行数")
    ap.add_argument("--no-headers", action="store_true", help="不打印表头 (tab/csv)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    try:
        cfg = load_env()
    except FileNotFoundError as e:
        sys.exit(str(e))

    if args.list_conns:
        for name in list_conns(cfg):
            c = select_conn(cfg, name)
            print("\t".join([
                name,
                c.get("DB_TYPE", ""),
                f"{c.get('DB_HOST', '')}:{c.get('DB_PORT', '')}",
                c.get("DB_DATABASE", ""),
            ]))
        return

    try:
        conn_cfg = select_conn(cfg, args.conn)
    except ValueError as e:
        sys.exit(str(e))

    if not conn_cfg.get("DB_PASSWORD"):
        sys.stderr.write(f"-- 提示: 连接 {args.conn or 'default'} 的密码为空\n")

    db_type = (conn_cfg.get("DB_TYPE") or "mysql").lower()
    driver = DRIVER_MAP.get(db_type)
    if driver is None:
        sys.exit(
            f"不支持的 DB_TYPE: {db_type}\n目前支持: {', '.join(DRIVER_MAP.keys())}"
        )

    try:
        import importlib
        importlib.import_module(driver)
    except ImportError:
        sys.exit(f"缺少驱动 {driver}, 请执行: pip install {driver}")

    sql, db_override = build_sql(args, driver)
    conn = connect(cfg, database=db_override, conn=args.conn)
    try:
        cur = conn.cursor()
        run_and_print(cur, sql, args.format, args.limit, not args.no_headers)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
