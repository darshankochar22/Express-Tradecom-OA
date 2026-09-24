import os
from urllib.parse import quote_plus


class Config:
    DB_USER = os.getenv("DB_USER", "app")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "app")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "users")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    DEFAULT_PAGE_LIMIT = 10
    MAX_PAGE_LIMIT = 100
