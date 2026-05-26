"""数据库访问与按目录划分的权限判断。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from werkzeug.security import check_password_hash

from config import Config

DB_PATH = Path(Config.DATABASE_PATH)
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def normalize_rel_path(rel_path: str) -> str:
    if not rel_path:
        return ""
    return rel_path.strip("/\\").replace("\\", "/")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema_sql)


def is_database_empty() -> bool:
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return count == 0


def verify_user(username: str, password: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, is_active FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row or not row["is_active"]:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return {"id": row["id"], "username": row["username"]}


def get_user_permissions(user_id: int) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT dp.path_prefix, dp.can_read, dp.can_write, dp.can_delete
            FROM directory_permissions dp
            JOIN user_roles ur ON ur.role_id = dp.role_id
            WHERE ur.user_id = ?
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "path_prefix": normalize_rel_path(r["path_prefix"]),
            "can_read": bool(r["can_read"]),
            "can_write": bool(r["can_write"]),
            "can_delete": bool(r["can_delete"]),
        }
        for r in rows
    ]


def _perm_allows(perm: dict, action: str) -> bool:
    if action == "read":
        return perm["can_read"]
    if action == "write":
        return perm["can_write"]
    if action == "delete":
        return perm["can_delete"]
    return False


def _path_matches_prefix(rel_path: str, prefix: str) -> bool:
    """目标路径在权限前缀之下（含自身）。"""
    rel_path = normalize_rel_path(rel_path)
    prefix = normalize_rel_path(prefix)
    if not prefix:
        return True
    return rel_path == prefix or rel_path.startswith(prefix + "/")


def _prefix_under_path(prefix: str, parent_path: str) -> bool:
    """权限前缀位于 parent_path 目录之内（用于列出上级目录中的子项）。"""
    parent_path = normalize_rel_path(parent_path)
    prefix = normalize_rel_path(prefix)
    if not parent_path:
        return True
    return prefix == parent_path or prefix.startswith(parent_path + "/")


def user_can(user_id: int, rel_path: str, action: str) -> bool:
    rel_path = normalize_rel_path(rel_path)
    perms = get_user_permissions(user_id)
    if not perms:
        return False

    for perm in perms:
        if not _perm_allows(perm, action):
            continue
        prefix = perm["path_prefix"]
        if not prefix:
            return True
        if _path_matches_prefix(rel_path, prefix):
            return True
    return False


def can_list_directory(user_id: int, rel_path: str) -> bool:
    """是否允许进入并列出该目录。"""
    rel_path = normalize_rel_path(rel_path)
    if not rel_path:
        return any(p["can_read"] for p in get_user_permissions(user_id))

    if user_can(user_id, rel_path, "read"):
        return True

    perms = get_user_permissions(user_id)
    for perm in perms:
        if not perm["can_read"]:
            continue
        if _prefix_under_path(perm["path_prefix"], rel_path):
            return True
    return False


def can_see_list_item(user_id: int, item_rel_path: str) -> bool:
    """列表中的文件/文件夹是否对用户可见。"""
    item_rel_path = normalize_rel_path(item_rel_path)
    if user_can(user_id, item_rel_path, "read"):
        return True

    perms = get_user_permissions(user_id)
    for perm in perms:
        if not perm["can_read"]:
            continue
        prefix = perm["path_prefix"]
        if prefix and prefix.startswith(item_rel_path + "/"):
            return True
    return False


def get_accessible_roots(user_id: int) -> List[str]:
    """用户可从根目录直接进入的顶层路径（用于前端）。"""
    perms = get_user_permissions(user_id)
    roots = set()
    for perm in perms:
        if not perm["can_read"]:
            continue
        prefix = perm["path_prefix"]
        if not prefix:
            return [""]
        roots.add(prefix.split("/")[0])
    return sorted(roots)


def get_directory_menu(user_id: int) -> List[dict]:
    """根据可读目录权限生成左侧菜单树。"""
    perms = [p for p in get_user_permissions(user_id) if p["can_read"]]
    if not perms:
        return []

    if any(not p["path_prefix"] for p in perms):
        return [{"path": "", "name": "全部文件", "children": []}]

    prefixes = sorted(
        {normalize_rel_path(p["path_prefix"]) for p in perms if p["path_prefix"]}
    )
    return _build_menu_tree(prefixes)


def _build_menu_tree(prefixes: List[str]) -> List[dict]:
    tree: dict = {}
    for prefix in prefixes:
        parts = prefix.split("/")
        node = tree
        for i, part in enumerate(parts):
            full_path = "/".join(parts[: i + 1])
            if part not in node:
                node[part] = {"_path": full_path, "_sub": {}}
            node = node[part]["_sub"]

    def to_list(node: dict) -> List[dict]:
        items = []
        for key in sorted(node.keys()):
            val = node[key]
            item = {"path": val["_path"], "name": key}
            children = to_list(val["_sub"])
            if children:
                item["children"] = children
            items.append(item)
        return items

    return to_list(tree)
