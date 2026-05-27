"""应用启动入口：负责读取运行配置并启动 Web 服务。"""
import os
from pathlib import Path

from file import app, BUSINESS_ROOT, BUSINESS_ROOT_ENV


def main():
    if BUSINESS_ROOT_ENV in os.environ:
        print(f"[配置] 业务文件根目录（来自环境变量）: {BUSINESS_ROOT}")
    else:
        print(f"[配置] 业务文件根目录（默认，未分离）: {BUSINESS_ROOT}")
        print(f"[提示] 如需分离代码与数据，请设置环境变量 {BUSINESS_ROOT_ENV}=<绝对路径>")

    # host = os.environ.get("HOST", "127.0.0.1")
    # port = int(os.environ.get("PORT", "5001"))
    # debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    #
    # print("文件管理系统后端已启动")
    # print(f"代码目录: {Path(__file__).parent.resolve()}")
    # print(f"业务数据根目录: {BUSINESS_ROOT}")
    # print(f"用户数据库: {app.config['DATABASE_PATH']}（初始化请运行 python init_db.py）")
    # print(f"请在浏览器中访问 http://{host}:{port}")

    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")

    print("文件管理系统后端已启动")
    print(f"代码目录: {Path(__file__).parent.resolve()}")
    print(f"业务数据根目录: {BUSINESS_ROOT}")
    print(f"用户数据库: {app.config['DATABASE_PATH']}（初始化请运行 python init_db.py）")
    print(f"请在浏览器中访问 http://{host}:{port}")
    
    uvicorn.run("file:app", host="127.0.0.1", port=5001, interface="wsgi", log_config="log_config.json", reload=False,)
