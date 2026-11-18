"""محرك الصلاحيات: تحقق وتنظيف الصلاحيات القادمة من الذكاء الاصطناعي"""
from typing import List

import discord

from app.schemas.server_design import ServerDesignSchema

BLOCKED_PERMISSIONS = {"ADMINISTRATOR"}
MAX_ROLES = 15
MAX_CHANNELS = 30


def is_valid_permission(name: str) -> bool:
    return name.lower() in discord.Permissions.VALID_FLAGS


def to_discord_permissions(names: List[str]) -> discord.Permissions:
    """تحويل أسماء الصلاحيات إلى discord.Permissions (يتجاهل غير الصالح والخطير)"""
    perms = discord.Permissions.none()
    for name in names:
        if name.upper() in BLOCKED_PERMISSIONS or not is_valid_permission(name):
            continue
        setattr(perms, name.lower(), True)
    return perms


def sanitize_design(design: ServerDesignSchema) -> List[str]:
    """ينظف التصميم في مكانه ويعيد قائمة تحذيرات"""
    warnings: List[str] = []

    if len(design.roles) > MAX_ROLES:
        warnings.append(f"تم تقليص الرتب إلى {MAX_ROLES}")
        design.roles = design.roles[:MAX_ROLES]
    if len(design.channels) > MAX_CHANNELS:
        warnings.append(f"تم تقليص الرومات إلى {MAX_CHANNELS}")
        design.channels = design.channels[:MAX_CHANNELS]

    for role in design.roles:
        clean = []
        for p in role.permissions:
            if p.upper() in BLOCKED_PERMISSIONS:
                warnings.append(f"تم حذف صلاحية {p} من رتبة {role.name}")
            elif not is_valid_permission(p):
                warnings.append(f"صلاحية غير معروفة {p} في رتبة {role.name}")
            else:
                clean.append(p.upper())
        role.permissions = clean

    return warnings
