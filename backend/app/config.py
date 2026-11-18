"""إعدادات التطبيق المركزية"""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # تطبيق
    APP_NAME: str = "AI Discord Server Builder"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: str = "http://localhost:3000"  # مفصولة بفواصل

    # قاعدة البيانات
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ai_builder"
    REDIS_URL: str = "redis://localhost:6379"

    # جلسات Redis
    REDIS_SESSION_PREFIX: str = "session:"
    SESSION_TTL_SECONDS: int = 60 * 24 * 7  # أسبوع

    # Discord
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"

    # تشفير التوكنات المخزنة (مفتاح مستقل عن SECRET_KEY)
    ENCRYPTION_KEY: str = ""
    ENCRYPTION_KEY_VERSION: int = 1
    ENCRYPTION_KEYS_LEGACY: str = ""  # JSON: {"1": "old-fernet-key", "2": "another-old-key"}

    # AI
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    AI_PROVIDER: str = "openai"  # openai | google
    AI_MODEL: str = "gpt-4o-mini"

    # الأمان
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # أسبوع


settings = Settings()