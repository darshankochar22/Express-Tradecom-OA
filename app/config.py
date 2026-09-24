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

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", "60"))
    RESET_TOKEN_EXPIRES_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRES_MINUTES", "15"))
    RESET_MAX_ATTEMPTS = int(os.getenv("RESET_MAX_ATTEMPTS", "5"))
    RESET_LOCKOUT_MINUTES = int(os.getenv("RESET_LOCKOUT_MINUTES", "15"))

    DEFAULT_PAGE_LIMIT = 10
    MAX_PAGE_LIMIT = 100
