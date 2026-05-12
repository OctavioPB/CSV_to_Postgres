import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "etl_db")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "etl_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "etl_pass")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'etl_user')}:{os.getenv('POSTGRES_PASSWORD', 'etl_pass')}"
        f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
        f"/{os.getenv('POSTGRES_DB', 'etl_db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))


class TestingConfig(Config):
    TESTING = True
    _test_db = os.getenv("TEST_POSTGRES_DB", "etl_test_db")
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER', 'etl_user')}:{os.getenv('POSTGRES_PASSWORD', 'etl_pass')}"
        f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}"
        f"/{_test_db}"
    )
