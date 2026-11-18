"""Dependencies مشتركة: المستخدم الحالي عبر JWT (cookie أو Bearer)"""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import decrypt_token
from app.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
SESSION_COOKIE = "session"


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    session: Optional[str] = Cookie(None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = creds.credentials if creds else session
    if not token:
        raise HTTPException(401, "غير مسجّل الدخول")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "جلسة غير صالحة")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "مستخدم غير موجود")
    return user


def discord_token(user: User) -> str:
    """توكن Discord المفكوك تشفيره للمستخدم"""
    token = decrypt_token(user.access_token)
    if not token:
        raise HTTPException(401, "سجّل الدخول مجدداً")
    return token