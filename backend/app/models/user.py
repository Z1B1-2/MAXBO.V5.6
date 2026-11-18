"""نموذج المستخدم"""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # Discord user ID
    username = Column(String(100), nullable=False)
    discriminator = Column(String(10), nullable=True)
    avatar = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=True)  # مشفّر (Fernet)
    refresh_token = Column(Text, nullable=True)  # مشفّر (Fernet)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    encryption_key_version = Column(Integer, nullable=True)  # إصدار المفتاح المستخدم في التشفير
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())