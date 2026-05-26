# file.py - 文件管理系统业务逻辑
import os
import shutil
import datetime
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_file, session, redirect
from werkzeug.utils import secure_filename

from config import Config
from db import (
    can_list_directory,
    can_see_list_item,
    get_accessible_roots,
    get_directory_menu,
    get_user_permissions,
    init_database,
    is_database_empty,
    normalize_rel_path,
    user_can,
    verify_user,
)

app = Flask(__name__)
app.config.from_object(Config)
app.config["JSON_AS_ASCII"] = False

BUSINESS_ROOT_ENV = "FILE_MANAGER_ROOT"
default_root = Path(__file__).parent / "BusinessData"
BUSINESS_ROOT = Path(os.environ.get(BUSINESS_ROOT_ENV, default_root)).resolve()
BUSINESS_ROOT.mkdir(parents=True, exist_ok=True)


def setup_database():
    init_database()
    if is_database_empty():
        from init_db import seed_data

        seed_data()


setup_database()


# ================= 认证与权限 =================
def get_current_user_id():
    return session.get("user_id")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user_id():
            return jsonify({"error": "请先登录"}), 401
        return f(*args, **kwargs)

    return decorated


def page_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user_id():
            return redirect("/?login=1")
        return f(*args, **kwargs)

    return decorated


    return jsonify({"error": "无权访问该目录或文件"}), 403


def require_path_permission(action: str, rel_path: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "请先登录"}), 401
    if not user_can(user_id, rel_path, action):
        return permission_denied()
    return None


# ================= 辅助函数 =================
def secure_path(relative_path: str) -> Path:
    if not relative_path:
        return BUSINESS_ROOT
    relative_path = relative_path.lstrip("/\\")
    if ".." in relative_path.split(os.sep):
        raise ValueError("非法路径: 禁止使用 ..")
    target = (BUSINESS_ROOT / relative_path).resolve()
    if not str(target).startswith(str(BUSINESS_ROOT.resolve())):
        raise ValueError("路径越界访问")
    return target


def format_file_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_file_info(path: Path, rel_path: str) -> dict:
    is_dir = path.is_dir()
    stat = path.stat()
    size = "-" if is_dir else format_file_size(stat.st_size)
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    user_id = get_current_user_id()
    perms = {}
    if user_id:
        perms = {
            "can_read": user_can(user_id, rel_path, "read"),
            "can_write": user_can(user_id, rel_path, "write"),
            "can_delete": user_can(user_id, rel_path, "delete"),
        }
    return {
        "name": path.name,
        "type": "dir" if is_dir else "file",
        "size": size,
        "modified": modified,
        "relative_path": rel_path,
        **perms,
    }


# ================= 前端页面 =================
@app.route("/")
def home():
    """公司首页"""
    return render_template(
        "home.html",
        company_name=app.config["COMPANY_NAME"],
        company_slogan=app.config["COMPANY_SLOGAN"],
        company_intro=app.config["COMPANY_INTRO"],
    )


@app.route("/files")
@page_login_required
def files():
    """文件管理系统（需登录）"""
    return render_template(
        "index.html",
        root_name=BUSINESS_ROOT.name,
        root_path=str(BUSINESS_ROOT),
        company_name=app.config["COMPANY_NAME"],
    )


# ================= API 接口 =================
@app.route("/api/list")
@login_required
def api_list():
    rel_path = normalize_rel_path(request.args.get("path", ""))
    user_id = get_current_user_id()

    try:
        if not can_list_directory(user_id, rel_path):
            return permission_denied()

        target_dir = secure_path(rel_path)
        if not target_dir.is_dir():
            return jsonify({"error": "目录不存在"}), 404

        items = []
        for item in target_dir.iterdir():
            try:
                item_rel_path = str(item.relative_to(BUSINESS_ROOT)).replace("\\", "/")
                if can_see_list_item(user_id, item_rel_path):
                    items.append(get_file_info(item, item_rel_path))
            except Exception:
                continue

        items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
        return jsonify(
            {
                "current_path": rel_path,
                "items": items,
                "parent_path": (
                    "/".join(rel_path.split("/")[:-1]) if rel_path else None
                ),
                "accessible_roots": get_accessible_roots(user_id),
                "directory_menu": get_directory_menu(user_id),
                "current_permissions": {
                    "can_read": True,
                    "can_write": user_can(user_id, rel_path, "write"),
                    "can_delete": user_can(user_id, rel_path, "delete"),
                },
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route("/api/auth/status")
def api_auth_status():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"logged_in": False, "username": None})

    perms = get_user_permissions(user_id)
    return jsonify(
        {
            "logged_in": True,
            "username": session.get("username"),
            "accessible_roots": get_accessible_roots(user_id),
            "directory_menu": get_directory_menu(user_id),
            "permissions": perms,
        }
    )


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = verify_user(username, password)
    if not user:
        return jsonify({"error": "用户名或密码错误"}), 401

    session.clear()
    session["logged_in"] = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify(
        {
            "success": True,
            "username": user["username"],
            "accessible_roots": get_accessible_roots(user["id"]),
            "directory_menu": get_directory_menu(user["id"]),
        }
    )


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/download")
@login_required
def api_download():
    rel_path = normalize_rel_path(request.args.get("path", ""))
    if not rel_path:
        return jsonify({"error": "路径参数缺失"}), 400

    denied = require_path_permission("read", rel_path)
    if denied:
        return denied

    try:
        target = secure_path(rel_path)
        if not target.is_file():
            return jsonify({"error": "目标不是文件或不存在"}), 404
        return send_file(target, as_attachment=True, download_name=target.name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    rel_path = normalize_rel_path(request.form.get("path", ""))
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "请选择文件"}), 400

    denied = require_path_permission("write", rel_path)
    if denied:
        return denied

    try:
        target_dir = secure_path(rel_path)
        if not target_dir.is_dir():
            return jsonify({"error": "目标目录不存在"}), 404

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({"error": "文件名非法"}), 400

        save_path = target_dir / filename
        if save_path.exists():
            save_path.unlink()
        file.save(save_path)
        return jsonify({"success": True, "message": "上传成功"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"上传失败: {str(e)}"}), 500


@app.route("/api/mkdir", methods=["POST"])
@login_required
def api_mkdir():
    data = request.get_json() or {}
    rel_path = normalize_rel_path(data.get("path", ""))
    folder_name = (data.get("name") or "").strip()
    if not folder_name:
        return jsonify({"error": "文件夹名称不能为空"}), 400

    denied = require_path_permission("write", rel_path)
    if denied:
        return denied

    try:
        if "/" in folder_name or "\\" in folder_name:
            return jsonify({"error": "文件夹名不能包含路径分隔符"}), 400

        parent_dir = secure_path(rel_path)
        if not parent_dir.is_dir():
            return jsonify({"error": "父目录不存在"}), 404

        new_dir = parent_dir / folder_name
        new_dir.mkdir(exist_ok=False)
        return jsonify({"success": True, "message": "创建成功"})
    except FileExistsError:
        return jsonify({"error": "同名文件夹已存在"}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@app.route("/api/delete", methods=["DELETE"])
@login_required
def api_delete():
    data = request.get_json() or {}
    rel_path = normalize_rel_path(data.get("path", ""))
    if not rel_path:
        return jsonify({"error": "路径参数缺失"}), 400

    denied = require_path_permission("delete", rel_path)
    if denied:
        return denied

    try:
        target = secure_path(rel_path)
        if not target.exists():
            return jsonify({"error": "文件或目录不存在"}), 404

        if target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
        return jsonify({"success": True, "message": "删除成功"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError:
        return jsonify({"error": "权限不足，无法删除"}), 403
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@app.route("/api/rename", methods=["PUT"])
@login_required
def api_rename():
    data = request.get_json() or {}
    rel_path = normalize_rel_path(data.get("path", ""))
    new_name = (data.get("new_name") or "").strip()
    if not rel_path or not new_name:
        return jsonify({"error": "参数缺失"}), 400
    if "/" in new_name or "\\" in new_name:
        return jsonify({"error": "新名称不能包含路径分隔符"}), 400

    denied = require_path_permission("write", rel_path)
    if denied:
        return denied

    try:
        target = secure_path(rel_path)
        if not target.exists():
            return jsonify({"error": "文件或目录不存在"}), 404

        parent = target.parent
        new_path = parent / new_name
        if new_path.exists():
            return jsonify({"error": "同名文件或目录已存在"}), 409

        target.rename(new_path)
        return jsonify({"success": True, "message": "重命名成功"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"重命名失败: {str(e)}"}), 500
