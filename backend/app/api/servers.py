"""مسارات إدارة السيرفرات"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import discord_token, get_current_user
from app.core.ai_engine import AIGenerationError, generate_server_design
from app.core.permission_engine import sanitize_design
from app.database import get_db
from app.models.audit import AuditLog
from app.models.server import DesignStatus, ServerDesign
from app.models.user import User
from app.schemas.server_design import DesignRequest, DesignResponse

router = APIRouter(prefix="/api/servers", tags=["servers"])

DISCORD_GUILDS_URL = "https://discord.com/api/v10/users/@me/guilds"
ADMINISTRATOR = 0x8
MANAGE_GUILD = 0x20


async def get_user_guilds(access_token: str) -> list:
    """جلب السيرفرات التي يديرها المستخدم من Discord"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            DISCORD_GUILDS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(401, "توكن Discord غير صالح، سجّل الدخول مجدداً")

    return [
        {"id": g["id"], "name": g["name"], "icon": g.get("icon"), "owner": g.get("owner", False)}
        for g in resp.json()
        if int(g.get("permissions", 0)) & (ADMINISTRATOR | MANAGE_GUILD)
    ]


@router.get("/")
async def list_servers(user: User = Depends(get_current_user)):
    """عرض سيرفرات المستخدم التي يمكنه إدارتها"""
    return {"servers": await get_user_guilds(discord_token(user))}


@router.post("/design", response_model=DesignResponse)
async def create_design(
    request: DesignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """إنشاء تصميم سيرفر جديد بواسطة الذكاء الاصطناعي"""
    guilds = await get_user_guilds(discord_token(user))
    guild = next((g for g in guilds if g["id"] == str(request.guild_id)), None)
    if not guild:
        raise HTTPException(403, "لا تملك صلاحية إدارة هذا السيرفر")

    try:
        design, warnings = await generate_server_design(request.description)
    except AIGenerationError:
        raise HTTPException(502, "فشل الذكاء الاصطناعي في توليد التصميم، حاول مرة أخرى")
    warnings += sanitize_design(design)

    db_design = ServerDesign(
        user_id=user.id,
        guild_id=request.guild_id,
        guild_name=guild["name"],
        user_description=request.description,
        design_json=design.model_dump(mode="json"),
        status=DesignStatus.PREVIEW,
    )
    db.add(db_design)
    await db.commit()
    await db.refresh(db_design)

    db.add(AuditLog(user_id=user.id, design_id=db_design.id, action="design_created", details={"warnings": warnings}))
    await db.commit()

    return DesignResponse(
        design_id=db_design.id,
        status=db_design.status.value,
        design=design,
        warnings=warnings,
    )


@router.get("/design/{design_id}", response_model=DesignResponse)
async def get_design(design_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """معاينة تصميم محفوظ"""
    from app.schemas.server_design import ServerDesignSchema

    d = await db.get(ServerDesign, design_id)
    if not d or d.user_id != user.id:
        raise HTTPException(404, "التصميم غير موجود")
    return DesignResponse(design_id=d.id, status=d.status.value, design=ServerDesignSchema(**d.design_json), warnings=[])
