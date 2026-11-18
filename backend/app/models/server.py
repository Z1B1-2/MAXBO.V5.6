"""نموذج السيرفر وتصميمه"""
import enum

from sqlalchemy import JSON, BigInteger, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.sql import func

from app.database import Base


class DesignStatus(str, enum.Enum):
    DRAFT = "draft"
    PREVIEW = "preview"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ServerDesign(Base):
    __tablename__ = "server_designs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    guild_name = Column(String(200), nullable=False)

    user_description = Column(Text, nullable=False)
    design_json = Column(JSON, nullable=False)
    status = Column(Enum(DesignStatus), default=DesignStatus.DRAFT)

    execution_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
