"""应用启动入口：负责读取运行配置并启动 Web 服务。"""
import os
from pathlib import Path

from file import app, BUSINESS_ROOT, BUSINESS_ROOT_ENV

# 运行配置（可被环境变量 HOST / PORT / FLASK_DEBUG 覆盖）
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
DEFAULT_DEBUG = False

LOG_CONFIG = Path(__file__).parent / "log_config.json"


def get_run_config():
    host = os.environ.get("HOST", DEFAULT_HOST)
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    debug = os.environ.get("FLASK_DEBUG", str(DEFAULT_DEBUG).lower()).lower() in ("1", "true", "yes")
    return host, port, debug


def print_startup_info(host, port):
    if BUSINESS_ROOT_ENV in os.environ:
        print(f"[配置] 业务文件根目录（来自环境变量）: {BUSINESS_ROOT}")
    else:
        print(f"[配置] 业务文件根目录（默认，未分离）: {BUSINESS_ROOT}")
        print(f"[提示] 如需分离代码与数据，请设置环境变量 {BUSINESS_ROOT_ENV}=<绝对路径>")

    print("文件管理系统后端已启动")
    print(f"代码目录: {Path(__file__).parent.resolve()}")
    print(f"业务数据根目录: {BUSINESS_ROOT}")
    print(f"上传账号: {app.config['AUTH_USERNAME']}（可通过环境变量 AUTH_USERNAME / AUTH_PASSWORD 修改）")
    print(f"请在浏览器中访问 http://{host}:{port}")


if __name__ == "__main__":
    import uvicorn

    host, port, debug = get_run_config()
    print_startup_info(host, port)

    # Flask 是 WSGI 应用：指向 file:app，并显式指定 interface="wsgi"
    uvicorn.run(
        "file:app",
        host=host,
        port=port,
        interface="wsgi",
        log_config=str(LOG_CONFIG),
        reload=debug,
    )
