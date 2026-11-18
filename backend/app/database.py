"""إعداد قاعدة البيانات (SQLAlchemy + asyncpg)"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """Dependency لجلسة قاعدة البيانات"""
    async with async_session() as session:
        yield session


async def init_db():
    """إنشاء الجداول عند التشغيل"""
    from app.models import audit, server, user  # noqa: F401  (تسجيل النماذج)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
