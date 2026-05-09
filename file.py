# app.py - 后端主程序
import os
import shutil
import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文显示

# 配置管理根目录，请根据实际情况修改此路径
# 默认使用当前目录下的 "ManagedRoot" 文件夹
BASE_DIR = Path(__file__).parent / "ManagedRoot"
BASE_DIR.mkdir(exist_ok=True)  # 确保根目录存在
"""测试github上传"""

def secure_path(relative_path: str) -> Path:
    """
    将相对路径转换为绝对路径，并确保其位于管理根目录内，防止路径遍历攻击
    :param relative_path: 用户请求的相对路径，例如 "docs/笔记.txt"
    :return: 安全的绝对路径
    :raises ValueError: 当路径越界时抛出
    """
    if not relative_path:
        return BASE_DIR
    # 移除开头的分隔符和多余的路径分隔符
    relative_path = relative_path.lstrip('/\\')
    if '..' in relative_path.split(os.sep):
        raise ValueError("非法路径: 禁止使用 ..")
    target = (BASE_DIR / relative_path).resolve()
    # 检查路径是否在 BASE_DIR 内
    if not str(target).startswith(str(BASE_DIR.resolve())):
        raise ValueError("路径越界访问")
    return target


def format_file_size(size_bytes: int) -> str:
    """将字节数转换为人类可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_file_info(path: Path, rel_path: str) -> dict:
    """获取单个文件或文件夹的详细信息"""
    is_dir = path.is_dir()
    stat = path.stat()
    if is_dir:
        # 目录不计算大小，避免耗时
        size = "-"
    else:
        size = format_file_size(stat.st_size)
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    return {
        "name": path.name,
        "type": "dir" if is_dir else "file",
        "size": size,
        "modified": modified,
        "relative_path": rel_path
    }


@app.route('/')
def index():
    """前端页面入口"""
    return render_template('index.html', root_name=BASE_DIR.name)


# ------------------- API 接口 -------------------
@app.route('/api/list')
def api_list():
    """列出指定目录下的内容"""
    rel_path = request.args.get('path', '')
    try:
        target_dir = secure_path(rel_path)
        if not target_dir.is_dir():
            return jsonify({"error": "目录不存在"}), 404

        items = []
        for item in target_dir.iterdir():
            # 忽略隐藏文件（可选，可根据需要修改）
            # if item.name.startswith('.'):
            #     continue
            try:
                # 计算该文件/目录相对于 BASE_DIR 的路径
                item_rel_path = str(item.relative_to(BASE_DIR)).replace('\\', '/')
                items.append(get_file_info(item, item_rel_path))
            except Exception:
                continue
        # 排序：文件夹在前，文件在后，按名称排序
        items.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
        return jsonify({
            "current_path": rel_path.replace('\\', '/'),
            "items": items,
            "parent_path": '/'.join(rel_path.replace('\\', '/').split('/')[:-1]) if rel_path else None
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"服务器错误: {str(e)}"}), 500


@app.route('/api/download')
def api_download():
    """下载文件（仅支持文件）"""
    rel_path = request.args.get('path', '')
    if not rel_path:
        return jsonify({"error": "路径参数缺失"}), 400
    try:
        target = secure_path(rel_path)
        if not target.is_file():
            return jsonify({"error": "目标不是文件或不存在"}), 404
        return send_file(target, as_attachment=True, download_name=target.name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """上传文件到指定目录"""
    rel_path = request.form.get('path', '')
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({"error": "请选择文件"}), 400

    try:
        target_dir = secure_path(rel_path)
        if not target_dir.is_dir():
            return jsonify({"error": "目标目录不存在"}), 404

        # 清理文件名，防止路径注入
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({"error": "文件名非法"}), 400

        save_path = target_dir / filename
        # 如果文件已存在，先删除再覆盖（可选，或提示冲突）
        if save_path.exists():
            save_path.unlink()
        file.save(save_path)
        return jsonify({"success": True, "message": "上传成功"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"上传失败: {str(e)}"}), 500


@app.route('/api/mkdir', methods=['POST'])
def api_mkdir():
    """创建新文件夹"""
    data = request.get_json()
    rel_path = data.get('path', '')
    folder_name = data.get('name', '').strip()
    if not folder_name:
        return jsonify({"error": "文件夹名称不能为空"}), 400

    try:
        # 不允许文件夹名包含路径分隔符
        if '/' in folder_name or '\\' in folder_name:
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


@app.route('/api/delete', methods=['DELETE'])
def api_delete():
    """删除文件或空目录（非空目录将递归删除）"""
    data = request.get_json()
    rel_path = data.get('path', '')
    if not rel_path:
        return jsonify({"error": "路径参数缺失"}), 400

    try:
        target = secure_path(rel_path)
        if not target.exists():
            return jsonify({"error": "文件或目录不存在"}), 404

        if target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)  # 递归删除文件夹
        return jsonify({"success": True, "message": "删除成功"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError:
        return jsonify({"error": "权限不足，无法删除"}), 403
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@app.route('/api/rename', methods=['PUT'])
def api_rename():
    """重命名文件或文件夹"""
    data = request.get_json()
    rel_path = data.get('path', '')
    new_name = data.get('new_name', '').strip()
    if not rel_path or not new_name:
        return jsonify({"error": "参数缺失"}), 400
    if '/' in new_name or '\\' in new_name:
        return jsonify({"error": "新名称不能包含路径分隔符"}), 400

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


if __name__ == '__main__':
    print(f"文件管理系统后端已启动，管理根目录为: {BASE_DIR.resolve()}")
    print("请在浏览器中访问 http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)

