"""إعدادات الاختبار المشتركة"""
import os


def pytest_configure():
    os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-bytes-long!!")
    os.environ.setdefault("ENCRYPTION_KEY_VERSION", "1")
    os.environ.setdefault("ENCRYPTION_KEYS_LEGACY", "{}")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
    os.environ.setdefault("DISCORD_BOT_TOKEN", "")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/ai_builder")