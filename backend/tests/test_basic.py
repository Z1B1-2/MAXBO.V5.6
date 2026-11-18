from app.core.ai_engine import _default_design
from app.core.permission_engine import sanitize_design
from app.schemas.server_design import RoleSchema, ServerDesignSchema


def test_default_design():
    d = _default_design("سيرفر للألعاب والمجتمع")
    assert d.roles and d.channels


def test_sanitize_removes_admin():
    d = ServerDesignSchema(
        server_name="x",
        roles=[RoleSchema(name="Boss", permissions=["ADMINISTRATOR", "SEND_MESSAGES", "FAKE_PERM"])],
    )
    warnings = sanitize_design(d)
    assert d.roles[0].permissions == ["SEND_MESSAGES"]
    assert len(warnings) == 2
