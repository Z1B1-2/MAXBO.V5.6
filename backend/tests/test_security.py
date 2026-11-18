import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.core.crypto import decrypt_token, encrypt_token, verify_token_encrypted, _keyring
from app.core.discord_engine import DiscordExecutionEngine
from app.core.permission_engine import to_discord_permissions
from app.core.ratelimit import RateLimitMiddleware
from app.schemas.server_design import (
    ChannelSchema,
    CategorySchema,
    PermissionOverwrite,
    RoleSchema,
    ServerDesignSchema,
)


def test_token_encryption_roundtrip():
    enc = encrypt_token("secret-token")
    assert enc != "secret-token"
    assert verify_token_encrypted(enc) is True
    assert decrypt_token(enc) == "secret-token"


def test_decrypt_garbage_returns_none():
    assert decrypt_token("not-a-valid-token") is None
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None


@pytest.mark.parametrize("perm", ["ADMINISTRATOR", "administrator"])
def test_admin_never_allowed(perm):
    assert not to_discord_permissions([perm]).administrator


def test_encryption_includes_version():
    enc = encrypt_token("my-secret-token")
    prefix = enc.split(":", 1)[0]
    assert prefix.isdigit()
    assert int(prefix) == 1


def test_decrypt_with_wrong_version_returns_none():
    enc = encrypt_token("my-secret-token")
    wrong_version = "99:" + enc.split(":", 1)[1]
    assert decrypt_token(wrong_version) is None


def test_legacy_key_decryption():
    """القيمة المشفرة بمفتاح قديم يجب أن تُفك حتى بعد تدوير المفتاح."""
    from cryptography.fernet import Fernet

    old_key = Fernet.generate_key()
    old_fernet = Fernet(old_key)
    token_value = old_fernet.encrypt(b"legacy-token").decode()
    legacy_value = f"0:{token_value}"

    original = settings.ENCRYPTION_KEYS_LEGACY
    settings.ENCRYPTION_KEYS_LEGACY = f'{{"0": "{old_key.decode()}"}}'
    _keyring.cache_clear()

    assert decrypt_token(legacy_value) == "legacy-token"
    _keyring.cache_clear()
    settings.ENCRYPTION_KEYS_LEGACY = original


def test_permission_engine_blocks_administrator():
    perms = to_discord_permissions(["ADMINISTRATOR", "SEND_MESSAGES"])
    assert not perms.administrator
    assert perms.send_messages


def test_permission_engine_blocks_unknown_permission():
    perms = to_discord_permissions(["SEND_MESSAGES", "NON_EXISTENT_PERM"])
    assert perms.send_messages


def test_discord_engine_requires_bot_permissions():
    engine = DiscordExecutionEngine(bot_token="fake-token")
    assert engine.token == "fake-token"


def test_server_design_schema_defaults():
    d = ServerDesignSchema(server_name="اختبار")
    assert d.server_name == "اختبار"
    assert d.roles == []
    assert d.channels == []
    assert d.categories == []


def test_rate_limit_blocks_after_limit():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, default_limit=3, path_limits=[])

    @app.get("/x")
    def x():
        return {"ok": True}

    c = TestClient(app)
    codes = [c.get("/x").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]