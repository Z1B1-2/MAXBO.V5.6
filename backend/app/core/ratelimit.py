"""Rate limiting بسيط في الذاكرة (لكل عملية). للإنتاج متعدد النسخ استخدم Redis."""
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

DEFAULT_LIMIT = 120  # طلب/دقيقة
PATH_LIMITS = [("/api/servers/design", 5), ("/api/builder", 10), ("/api/auth", 20)]
WINDOW = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_limit: int = DEFAULT_LIMIT, path_limits=None):
        super().__init__(app)
        self.default_limit = default_limit
        self.path_limits = PATH_LIMITS if path_limits is None else path_limits
        self.hits = defaultdict(deque)

    async def dispatch(self, request, call_next):
        path = request.url.path
        limit, bucket = self.default_limit, "default"
        for prefix, lim in self.path_limits:
            if path.startswith(prefix):
                limit, bucket = lim, prefix
                break

        ip = request.client.host if request.client else "unknown"
        q = self.hits[(ip, bucket)]
        now = time.monotonic()
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "طلبات كثيرة، حاول لاحقاً"}, status_code=429, headers={"Retry-After": str(WINDOW)})
        q.append(now)
        return await call_next(request)
