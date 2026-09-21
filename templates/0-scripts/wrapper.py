"""
sql-query 项目薄壳模板

复制到业务项目的 0-scripts/wrapper.py 后使用。
它只负责把当前项目的 .env 路径传给共享 sql-query skill 脚本。

skill 脚本查找顺序:
  1. 环境变量 SQL_QUERY_SKILL (指向 scripts/db_query.py 的绝对路径)
  2. 下方 SKILL_CANDIDATES 里第一个实际存在的路径
找不到时再报错, 并提示如何用 SQL_QUERY_SKILL 覆盖。
换电脑 / 换目录时通常不用改本文件, 加一条候选路径或设环境变量即可。
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# 常见安装位置, 按优先级排列; 末尾的 ~/code 是 README 里的通用约定路径
SKILL_CANDIDATES = [
    r"D:/Consun/Code/claude-skills/sql-query/scripts/db_query.py",
    os.path.expanduser("~/code/claude-skills/sql-query/scripts/db_query.py"),
]


def find_skill_script():
    override = os.environ.get("SQL_QUERY_SKILL")
    if override:
        return os.path.normpath(os.path.expanduser(override))
    for cand in SKILL_CANDIDATES:
        if os.path.exists(cand):
            return os.path.normpath(cand)
    return None


def main():
    skill_script = find_skill_script()
    if not skill_script:
        sys.exit(
            "找不到 sql-query skill 脚本。已尝试:\n"
            + "\n".join(f"  - {c}" for c in SKILL_CANDIDATES)
            + "\n请确认 skill 已克隆到本地, 或设环境变量 SQL_QUERY_SKILL 指向 scripts/db_query.py"
        )

    env = os.environ.copy()
    env.setdefault("SQL_QUERY_ENV_PATH", PROJECT_ENV_PATH)

    result = subprocess.run([sys.executable, skill_script] + sys.argv[1:], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
