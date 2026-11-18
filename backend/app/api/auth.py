"""مسارات المصادقة عبر Discord OAuth2"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ALGORITHM, SESSION_COOKIE, bearer
from app.config import settings
from app.core.crypto import encrypt_token
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/v10/users/@me"


@router.get("/login")
async def login():
    """إعادة التوجيه لتسجيل الدخول عبر Discord"""
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {"n": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email guilds",
        "state": state,
    }
    resp = RedirectResponse(f"{DISCORD_AUTH_URL}?{urlencode(params)}")
    resp.set_cookie("oauth_nonce", nonce, max_age=600, httponly=True, samesite="lax", secure=not settings.DEBUG)
    return resp


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    oauth_nonce: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """استقبال code من Discord، حفظ المستخدم، وإصدار JWT"""
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(400, "state غير صالح")
    if not oauth_nonce or not secrets.compare_digest(payload.get("n", ""), oauth_nonce):
        raise HTTPException(400, "فشل التحقق من state")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, "فشل تسجيل الدخول")
        tokens = token_resp.json()

        user_resp = await client.get(
            DISCORD_USER_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(400, "تعذر جلب بيانات المستخدم")
        data = user_resp.json()

    user = await db.get(User, int(data["id"]))
    if not user:
        user = User(id=int(data["id"]), username=data["username"])
        db.add(user)
    user.username = data["username"]
    user.avatar = data.get("avatar")
    user.email = data.get("email")
    user.access_token = encrypt_token(tokens["access_token"])
    user.refresh_token = encrypt_token(tokens.get("refresh_token"))
    user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 0))
    user.encryption_key_version = settings.ENCRYPTION_KEY_VERSION
    await db.commit()

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jwt_token = jwt.encode({"sub": str(user.id), "exp": expire}, settings.SECRET_KEY, algorithm=ALGORITHM)

    resp = JSONResponse({"user": {"id": str(user.id), "username": user.username, "avatar": user.avatar}})
    resp.set_cookie(
        SESSION_COOKIE,
        jwt_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    resp.delete_cookie("oauth_nonce")
    return resp


@router.post("/refresh")
async def refresh_token(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    session: Optional[str] = Cookie(None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
):
    """تجديد JWT الجلسة."""
    from app.api.deps import discord_token as _  # noqa: F401

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

    new_expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_jwt = jwt.encode({"sub": str(user.id), "exp": new_expire}, settings.SECRET_KEY, algorithm=ALGORITHM)

    resp = JSONResponse({"user": {"id": str(user.id), "username": user.username, "avatar": user.avatar}})
    resp.set_cookie(
        SESSION_COOKIE,
        new_jwt,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return resp


@router.post("/logout")
async def logout():
    """إلغاء الجلسة وحذف الكوكي."""
    resp = JSONResponse({"message": "تم تسجيل الخروج"})
    resp.delete_cookie(SESSION_COOKIE)
    resp.delete_cookie("oauth_nonce")
    return resp