"""初始化数据库表结构并写入示例用户、角色、目录权限。"""
import os
from pathlib import Path

from werkzeug.security import generate_password_hash

from config import Config
from db import get_connection, init_database, is_database_empty, normalize_rel_path

BUSINESS_ROOT = Path(
    os.environ.get("FILE_MANAGER_ROOT", Path(__file__).parent / "BusinessData")
).resolve()


def seed_data():
    roles = [
        ("admin", "系统管理员，全部目录"),
        ("hr", "人力资源部目录"),
        ("finance", "财务部目录（只读）"),
        ("public", "公共目录"),
    ]
    permissions = [
        ("admin", "", 1, 1, 1),
        ("hr", "dept-hr", 1, 1, 1),
        ("finance", "dept-finance", 1, 0, 0),
        ("public", "public", 1, 1, 0),
    ]
    users = [
        ("admin", "admin123", ["admin"]),
        ("hr_user", "hr123", ["hr"]),
        ("finance_user", "finance123", ["finance"]),
        ("guest", "guest123", ["public"]),
    ]

    with get_connection() as conn:
        for name, desc in roles:
            conn.execute(
                "INSERT INTO roles (name, description) VALUES (?, ?)",
                (name, desc),
            )

        role_ids = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM roles").fetchall()
        }

        for role_name, prefix, r, w, d in permissions:
            conn.execute(
                """
                INSERT INTO directory_permissions
                (role_id, path_prefix, can_read, can_write, can_delete)
                VALUES (?, ?, ?, ?, ?)
                """,
                (role_ids[role_name], normalize_rel_path(prefix), r, w, d),
            )

        for username, password, role_names in users:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()["id"]
            for rn in role_names:
                conn.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)",
                    (user_id, role_ids[rn]),
                )

    BUSINESS_ROOT.mkdir(parents=True, exist_ok=True)
    for subdir in ("dept-hr", "dept-finance", "public"):
        (BUSINESS_ROOT / subdir).mkdir(parents=True, exist_ok=True)
    (BUSINESS_ROOT / "dept-hr" / "示例.txt").write_text(
        "HR 部门示例文件\n", encoding="utf-8"
    )
    (BUSINESS_ROOT / "dept-finance" / "报表.txt").write_text(
        "财务部示例文件（只读账号可下载）\n", encoding="utf-8"
    )
    (BUSINESS_ROOT / "public" / "readme.txt").write_text(
        "公共目录示例\n", encoding="utf-8"
    )


def main():
    init_database()
    if is_database_empty():
        seed_data()
        print(f"数据库已创建并写入示例数据: {Config.DATABASE_PATH}")
    else:
        print(f"数据库已存在，跳过种子数据: {Config.DATABASE_PATH}")
    print("\n示例账号：")
    print("  admin / admin123          -> 全部目录")
    print("  hr_user / hr123           -> dept-hr 读写删")
    print("  finance_user / finance123 -> dept-finance 只读")
    print("  guest / guest123          -> public 读写")


if __name__ == "__main__":
    main()
