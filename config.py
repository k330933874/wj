import os
from pathlib import Path

class Config:
    # 业务根目录：优先环境变量，否则使用代码目录下的 ./BusinessData
    BUSINESS_ROOT = Path(os.environ.get("FILE_MANAGER_ROOT",
                                         Path(__file__).parent / "BusinessData")).resolve()

    # 会话密钥（生产环境请通过环境变量 SECRET_KEY 设置）
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    # SQLite 数据库路径
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent / "data" / "file_manager.db"),
    )

    # 公司首页展示信息（可通过环境变量覆盖）
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "67科技")
    COMPANY_SLOGAN = os.environ.get("COMPANY_SLOGAN", "专注检测")
    COMPANY_INTRO = os.environ.get(
        "COMPANY_INTRO",
        "67科技致力于为企业提供安全、高效、可追溯的文件归档与协作解决方案，"
        "帮助组织规范资料管理流程，提升业务协同效率。",
    )