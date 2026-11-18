"""محرك الذكاء الاصطناعي لتحليل وصف المستخدم وتوليد تصميم السيرفر"""
import json

from app.config import settings
from app.schemas.server_design import ServerDesignSchema

SYSTEM_PROMPT = """أنت مهندس سيرفرات Discord محترف.
مهمتك تحويل وصف المستخدم إلى تصميم JSON منظم لسيرفر Discord.

المخرجات يجب أن تكون JSON فقط وفق هذا البناء:
{
  "server_name": "اسم السيرفر",
  "description": "وصف مختصر",
  "roles": [{"name": "اسم الرتبة", "color": "#HEX", "hoist": false, "permissions": []}],
  "categories": [{"name": "اسم التصنيف", "position": 0}],
  "channels": [{"name": "اسم الروم", "type": "text|voice|announcement", "category": "اسم التصنيف", "topic": "", "slowmode": 0}],
  "welcome_channel": "اسم روم الترحيب",
  "rules_channel": "اسم روم القوانين"
}

القواعد:
- لا تنشئ رتباً بصلاحيات خطيرة (ADMINISTRATOR) إلا إذا طلبها المستخدم صراحة
- لا تنشئ أكثر من 15 رتبة و 30 روم
- استخدم أسماء عربية أو إنجليزية حسب وصف المستخدم
- لا تضع أي نص خارج JSON
"""


class AIGenerationError(Exception):
    """فشل مزود الذكاء الاصطناعي (لا نستبدله بتصميم وهمي)"""


async def generate_server_design(description: str) -> tuple[ServerDesignSchema, list[str]]:
    """يعيد (التصميم، تحذيرات). عند فشل المزود يرفع AIGenerationError."""
    try:
        if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            return await _generate_openai(description), []
        if settings.AI_PROVIDER == "google" and settings.GOOGLE_API_KEY:
            return await _generate_google(description), []
    except Exception as e:
        raise AIGenerationError(str(e)) from e
    return _default_design(description), [
        "الذكاء الاصطناعي غير مُفعّل: هذا تصميم افتراضي ولا يعتمد على وصفك"
    ]


async def _generate_openai(description: str) -> ServerDesignSchema:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.AI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": description},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    data = json.loads(response.choices[0].message.content)
    return ServerDesignSchema(**data)


async def _generate_google(description: str) -> ServerDesignSchema:
    from google import genai  # حزمة google-genai

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    response = await client.aio.models.generate_content(
        model=settings.AI_MODEL,
        contents=f"{SYSTEM_PROMPT}\n\nوصف المستخدم:\n{description}",
        config={"response_mime_type": "application/json"},
    )
    data = json.loads(response.text)
    return ServerDesignSchema(**data)


def _default_design(description: str) -> ServerDesignSchema:
    """تصميم افتراضي عند عدم توفر ذكاء اصطناعي"""
    return ServerDesignSchema(
        server_name="سيرفر جديد",
        description=description[:200],
        roles=[
            {"name": "Admin", "color": "#E74C3C", "hoist": True, "permissions": ["MANAGE_GUILD"]},
            {"name": "Member", "color": "#2ECC71", "hoist": True, "permissions": ["SEND_MESSAGES"]},
        ],
        categories=[{"name": "عام", "position": 0}],
        channels=[
            {"name": "عام", "type": "text", "category": "عام"},
            {"name": "القوانين", "type": "text", "category": "عام"},
        ],
        welcome_channel="عام",
        rules_channel="القوانين",
    )
