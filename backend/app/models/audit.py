"""سجل التدقيق: من فعل ماذا ومتى"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    design_id = Column(BigInteger, ForeignKey("server_designs.id"), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
