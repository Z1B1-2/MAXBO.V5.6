"""مسارات الموافقة والتنفيذ (Milestone 3)"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import discord_token, get_current_user
from app.api.servers import get_user_guilds
from app.config import settings
from app.core.discord_engine import DiscordExecutionEngine, bot_in_guild
from app.core.permission_engine import sanitize_design
from app.database import async_session, get_db
from app.models.audit import AuditLog
from app.models.server import DesignStatus, ServerDesign
from app.models.user import User
from app.schemas.server_design import ServerDesignSchema

router = APIRouter(prefix="/api/builder", tags=["builder"])


async def _get_own_design(db: AsyncSession, design_id: int, user: User) -> ServerDesign:
    design = await db.get(ServerDesign, design_id)
    if not design or design.user_id != user.id:
        raise HTTPException(404, "التصميم غير موجود")
    return design


async def _require_bot(guild_id: int):
    if not await bot_in_guild(guild_id):
        raise HTTPException(409, "البوت غير مضاف لهذا السيرفر، أضفه أولاً")


@router.post("/{design_id}/approve")
async def approve(design_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    design = await _get_own_design(db, design_id, user)
    if design.status != DesignStatus.PREVIEW:
        raise HTTPException(409, f"لا يمكن الموافقة في الحالة: {design.status.value}")
    await _require_bot(design.guild_id)
    design.status = DesignStatus.APPROVED
    db.add(AuditLog(user_id=user.id, design_id=design.id, action="approved"))
    await db.commit()
    return {"design_id": design.id, "status": design.status.value}


async def _run_execution(design_id: int, user_id: int):
    async with async_session() as db:
        design = await db.get(ServerDesign, design_id)
        try:
            schema = ServerDesignSchema(**design.design_json)
            sanitize_design(schema)
            engine = DiscordExecutionEngine(settings.DISCORD_BOT_TOKEN)
            result = await engine.execute_design(design.guild_id, schema)
            design.execution_result = result
            design.status = DesignStatus.FAILED if result["errors"] else DesignStatus.COMPLETED
        except Exception as e:
            design.status = DesignStatus.FAILED
            design.error_message = str(e)
        db.add(
            AuditLog(
                user_id=user_id,
                design_id=design_id,
                action="execution_finished",
                details={"status": design.status.value, "result": design.execution_result, "error": design.error_message},
            )
        )
        await db.commit()


@router.post("/{design_id}/execute")
async def execute(
    design_id: int,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    design = await _get_own_design(db, design_id, user)
    if design.status != DesignStatus.APPROVED:
        raise HTTPException(409, "يجب الموافقة على التصميم أولاً (أو أنه نُفّذ مسبقاً)")

    guilds = await get_user_guilds(discord_token(user))
    if not any(g["id"] == str(design.guild_id) for g in guilds):
        raise HTTPException(403, "لا تملك صلاحية إدارة هذا السيرفر")
    await _require_bot(design.guild_id)

    # حجز ذرّي: طلب مكرر لن ينجح لأن الحالة لم تعد APPROVED
    res = await db.execute(
        update(ServerDesign)
        .where(ServerDesign.id == design.id, ServerDesign.status == DesignStatus.APPROVED)
        .values(status=DesignStatus.EXECUTING)
    )
    if res.rowcount == 0:
        await db.rollback()
        raise HTTPException(409, "التنفيذ بدأ بالفعل")
    db.add(AuditLog(user_id=user.id, design_id=design.id, action="execution_started"))
    await db.commit()

    background.add_task(_run_execution, design.id, user.id)
    return {"design_id": design.id, "status": DesignStatus.EXECUTING.value}


@router.get("/{design_id}/status")
async def status(design_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    design = await _get_own_design(db, design_id, user)
    return {
        "design_id": design.id,
        "status": design.status.value,
        "result": design.execution_result,
        "error": design.error_message,
    }
