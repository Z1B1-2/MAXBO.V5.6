"""Pydantic schemas للتصميم"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    CATEGORY = "category"
    ANNOUNCEMENT = "announcement"


class PermissionOverwrite(BaseModel):
    role_name: str
    allow: List[str] = []
    deny: List[str] = []


class ChannelSchema(BaseModel):
    name: str
    type: ChannelType = ChannelType.TEXT
    category: Optional[str] = None
    topic: Optional[str] = None
    slowmode: int = 0
    nsfw: bool = False
    permission_overwrites: List[PermissionOverwrite] = []


class RoleSchema(BaseModel):
    name: str
    color: str = "#99AAB5"
    hoist: bool = False
    mentionable: bool = False
    permissions: List[str] = []


class CategorySchema(BaseModel):
    name: str
    position: int = 0
    permission_overwrites: List[PermissionOverwrite] = []


class ServerDesignSchema(BaseModel):
    """Schema الناتج من الذكاء الاصطناعي"""
    server_name: str
    description: str = ""
    roles: List[RoleSchema] = []
    categories: List[CategorySchema] = []
    channels: List[ChannelSchema] = []
    welcome_channel: Optional[str] = None
    rules_channel: Optional[str] = None


class DesignRequest(BaseModel):
    """طلب تصميم جديد"""
    guild_id: int
    description: str = Field(..., min_length=10, max_length=2000)


class DesignResponse(BaseModel):
    design_id: int
    status: str
    design: ServerDesignSchema
    warnings: List[str] = []
