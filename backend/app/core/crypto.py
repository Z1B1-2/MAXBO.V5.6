"""تشفير التوكنات المخزنة (Fernet، مفتاح مستقل عن SECRET_KEY مع دعم إصدار المفتاح والتدوير)."""
import base64
import hashlib
import json
import logging
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_key(raw_key: str) -> bytes:
    """يُعيد 32 بايت بصيغة base64 url-safe صالحة لـ Fernet.
    يقبل مفتاح Fernet جاهزاً (يُعاد كما هو) أو نصاً عشوائياً يُشتق منه المفتاح."""
    raw_key = raw_key.strip()
    if not raw_key:
        raise ValueError("ENCRYPTION_KEY غير مضبوط")
    try:
        Fernet(raw_key.encode())
        return raw_key.encode()
    except (ValueError, TypeError):
        if len(raw_key) < 32:
            raise ValueError("ENCRYPTION_KEY قصير جداً (32 حرفاً على الأقل)")
        return base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())


@lru_cache(maxsize=None)
def _keyring() -> dict[int, Fernet]:
    """يُعيد حلقة مفاتيح: {الإصدار: Fernet instance}."""
    ring: dict[int, Fernet] = {}

    current_version = settings.ENCRYPTION_KEY_VERSION
    try:
        current_key = _normalize_key(settings.ENCRYPTION_KEY)
        ring[current_version] = Fernet(current_key)
    except ValueError as exc:
        logger.error("ENCRYPTION_KEY غير صالح: %s", exc)

    try:
        legacy = json.loads(settings.ENCRYPTION_KEYS_LEGACY) if settings.ENCRYPTION_KEYS_LEGACY else {}
        if isinstance(legacy, dict):
            for ver_str, key in legacy.items():
                try:
                    ring[int(ver_str)] = Fernet(_normalize_key(str(key)))
                except ValueError:
                    logger.warning("مفتاح تشفير قديم غير صالح للإصدار %s", ver_str)
    except json.JSONDecodeError:
        logger.warning("ENCRYPTION_KEYS_LEGACY ليس JSON صالحاً")

    return ring


def encrypt_token(value: Optional[str]) -> Optional[str]:
    """يشفر القيمة ويعيد "الإصدار:القيمة_المشفرة"."""
    if not value:
        return None
    ring = _keyring()
    if settings.ENCRYPTION_KEY_VERSION not in ring:
        raise ValueError(f"مفتاح التشفير للإصدار {settings.ENCRYPTION_KEY_VERSION} غير متوفر")
    token = ring[settings.ENCRYPTION_KEY_VERSION].encrypt(value.encode()).decode()
    return f"{settings.ENCRYPTION_KEY_VERSION}:{token}"


def decrypt_token(value: Optional[str]) -> Optional[str]:
    """يفك تشفير القيمة ويعيد النص الأصلي، أو None إذا لم يمكن الفك."""
    if not value:
        return None

    parts = value.split(":", 1)
    if len(parts) == 2:
        version_str, token_value = parts
        try:
            version = int(version_str)
        except ValueError:
            version = None
    else:
        version = None
        token_value = parts[0]

    ring = _keyring()

    # إذا كان الإصدار محدداً: استخدم مفتاح ذلك الإصدار فقط (لا fallback)
    if version is not None:
        if version in ring:
            try:
                return ring[version].decrypt(token_value.encode()).decode()
            except InvalidToken:
                return None
        return None

    # إذا لم يُحدد إصدار (قيمة قديمة): جرّب جميع المفاتيح
    for fernet in ring.values():
        try:
            return fernet.decrypt(token_value.encode()).decode()
        except InvalidToken:
            continue

    return None


def verify_token_encrypted(value: Optional[str]) -> bool:
    """يُعيد True إذا كانت القيمة مشفرة (تحتوي على الإصدار) وإلا False."""
    if not value:
        return False
    parts = value.split(":", 1)
    if len(parts) != 2:
        return False
    try:
        int(parts[0])
        return True
    except ValueError:
        return False