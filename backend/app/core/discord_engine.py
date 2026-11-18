"""محرك تنفيذ التصميم على Discord (عبر REST بدون تشغيل البوت كاملاً)"""
import asyncio
import logging
from typing import Dict, List

import discord
import httpx

from app.config import settings
from app.core.permission_engine import BLOCKED_PERMISSIONS, is_valid_permission, to_discord_permissions
from app.schemas.server_design import ChannelType, PermissionOverwrite, ServerDesignSchema

logger = logging.getLogger(__name__)


def _parse_color(color_hex: str) -> discord.Colour:
    """يحلل لون HEX (#RRGGBB أو RRGGBB). إذا فشل يعيد لوناً افتراضياً."""
    try:
        return discord.Colour(int(color_hex.lstrip("#"), 16))
    except (ValueError, TypeError):
        logger.warning("لون غير صالح: %s، استخدام اللون الافتراضي", color_hex)
        return discord.Colour.default()


def _build_overwrites(
    guild: discord.Guild,
    role_map: Dict[str, discord.Role],
    overwrites: List[PermissionOverwrite],
    errors: List[str],
) -> dict:
    """تحويل permission_overwrites إلى صيغة discord.py"""
    out = {}
    for ow in overwrites:
        target = guild.default_role if ow.role_name in ("@everyone", "everyone") else role_map.get(ow.role_name)
        if not target:
            errors.append(f"رتبة غير موجودة في الصلاحيات: {ow.role_name}")
            continue
        flags = {}
        for p in ow.allow:
            if p.upper() not in BLOCKED_PERMISSIONS and is_valid_permission(p):
                flags[p.lower()] = True
        for p in ow.deny:
            if is_valid_permission(p):
                flags[p.lower()] = False
        out[target] = discord.PermissionOverwrite(**flags)
    return out


async def bot_in_guild(guild_id: int) -> bool:
    """هل البوت مضاف للسيرفر؟"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://discord.com/api/v10/guilds/{guild_id}",
            headers={"Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}"},
        )
    return resp.status_code == 200


class DiscordExecutionEngine:
    """تنفيذ تصميم السيرفر عبر Discord API"""

    def __init__(self, bot_token: str):
        self.token = bot_token

    async def execute_design(self, guild_id: int, design: ServerDesignSchema) -> dict:
        results = {"roles": [], "categories": [], "channels": [], "errors": [], "warnings": []}

        client = discord.Client(intents=discord.Intents.none())
        try:
            await client.login(self.token)
            try:
                guild = await client.fetch_guild(guild_id)
            except discord.HTTPException:
                results["errors"].append(f"السيرفر {guild_id} غير موجود أو البوت غير مضاف له")
                return results

            # تعبئة كاش الرتب والأعضاء قبل أي مقارنة
            roles = await guild.fetch_roles()
            me = await guild.fetch_member(client.user.id)

            if not me:
                results["errors"].append("البوت غير موجود في قائمة أعضاء السيرفر")
                return results

            bot_perms = me.guild_permissions
            if not (bot_perms.manage_roles and bot_perms.manage_channels):
                results["errors"].append("البوت يحتاج صلاحيتي Manage Roles و Manage Channels")
                return results

            # التحقق من هيراركية الرتب: أعلى رتبة للبوت يجب أن تكون أعلى من @everyone
            top_role = max(me.roles, key=lambda r: r.position, default=guild.default_role)
            if top_role.position <= guild.default_role.position:
                results["errors"].append("أعلى رتبة للبوت ليست أعلى من @everyone (لا يمكنه إدارة رتب)")
                return results

            existing_channels = await guild.fetch_channels()
            existing_channel_names = {c.name.lower() for c in existing_channels}

            # 1. الرتب
            role_map: Dict[str, discord.Role] = {r.name: r for r in roles}
            for role_data in design.roles:
                if role_data.name in role_map:
                    results["roles"].append(f"موجود: {role_data.name}")
                    continue
                wanted = to_discord_permissions(role_data.permissions)
                allowed = discord.Permissions(wanted.value & bot_perms.value)  # لا يمكن منح ما لا يملكه البوت
                if allowed.value != wanted.value:
                    results["warnings"].append(f"رتبة {role_data.name}: حُذفت صلاحيات لا يملكها البوت")
                try:
                    role_map[role_data.name] = await guild.create_role(
                        name=role_data.name,
                        colour=_parse_color(role_data.color),
                        hoist=role_data.hoist,
                        mentionable=role_data.mentionable,
                        permissions=allowed,
                    )
                    results["roles"].append(f"تم إنشاء: {role_data.name}")
                    await asyncio.sleep(0.5)  # تجنب rate limits
                except Exception as e:
                    results["errors"].append(f"فشل إنشاء رتبة {role_data.name}: {e}")

            # 2. التصنيفات
            category_map = {c.name: c for c in existing_channels if isinstance(c, discord.CategoryChannel)}
            for cat_data in design.categories:
                if cat_data.name in category_map:
                    results["categories"].append(f"موجود: {cat_data.name}")
                    continue
                try:
                    category_map[cat_data.name] = await guild.create_category(
                        name=cat_data.name,
                        position=cat_data.position,
                        overwrites=_build_overwrites(guild, role_map, cat_data.permission_overwrites, results["errors"]),
                    )
                    results["categories"].append(f"تم إنشاء: {cat_data.name}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    results["errors"].append(f"فشل إنشاء تصنيف {cat_data.name}: {e}")

            # 3. الرومات
            for ch_data in design.channels:
                # منع التكرار عند إعادة المحاولة (idempotency مبدئية)
                if ch_data.name.lower() in existing_channel_names:
                    results["channels"].append(f"موجود بالفعل: {ch_data.name}")
                    continue
                try:
                    category = category_map.get(ch_data.category) if ch_data.category else None
                    overwrites = _build_overwrites(guild, role_map, ch_data.permission_overwrites, results["errors"])
                    if ch_data.type == ChannelType.VOICE:
                        await guild.create_voice_channel(name=ch_data.name, category=category, overwrites=overwrites)
                    else:
                        await guild.create_text_channel(
                            name=ch_data.name,
                            category=category,
                            topic=ch_data.topic or None,
                            slowmode_delay=ch_data.slowmode,
                            nsfw=ch_data.nsfw,
                            overwrites=overwrites,
                        )
                    results["channels"].append(f"تم إنشاء: {ch_data.name}")
                    await asyncio.sleep(0.5)  # تجنب rate limits
                except Exception as e:
                    results["errors"].append(f"فشل إنشاء روم {ch_data.name}: {e}")

        except Exception as e:
            results["errors"].append(f"خطأ عام: {e}")
            logger.exception("فشل تنفيذ التصميم للسيرفر %s", guild_id)
        finally:
            await client.close()

        return results