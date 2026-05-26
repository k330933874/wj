import os
from pathlib import Path

class Config:
    # 业务根目录：优先环境变量，否则使用代码目录下的 ./BusinessData
    BUSINESS_ROOT = Path(os.environ.get("FILE_MANAGER_ROOT",
                                         Path(__file__).parent / "BusinessData")).resolve()

    # 会话密钥（生产环境请通过环境变量 SECRET_KEY 设置）
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # 上传权限账号（生产环境请通过环境变量设置）
    AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
    AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin123")