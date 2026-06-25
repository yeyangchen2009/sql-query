"""
sql-query 项目薄壳模板

复制到业务项目的 0-scripts/wrapper.py 后使用。
它只负责把当前项目的 .env 路径传给共享 sql-query skill 脚本。
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

SKILL_SCRIPT = os.environ.get(
    "SQL_QUERY_SKILL",
    os.path.expanduser("~/code/claude-skills/sql-query/scripts/db_query.py"),
)


def main():
    if not os.path.exists(SKILL_SCRIPT):
        sys.exit(
            f"找不到 sql-query skill 脚本: {SKILL_SCRIPT}\n"
            f"请确认 skill 仓库已克隆到本地，或设置环境变量 SQL_QUERY_SKILL 指向 scripts/db_query.py"
        )

    env = os.environ.copy()
    env.setdefault("SQL_QUERY_ENV_PATH", PROJECT_ENV_PATH)

    result = subprocess.run([sys.executable, SKILL_SCRIPT] + sys.argv[1:], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
