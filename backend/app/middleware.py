"""Pure-ASGI middleware (safe for SSE streaming): access log, API-key auth, rate limiting, signed file links."""
import hashlib
import hmac
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

log = logging.getLogger("app.access")

EXEMPT_EXACT = {"/health", "/openapi.json", "/redoc"}
EXEMPT_PREFIX = ("/docs",)
HEAVY = re.compile(r"^/api/(research(/stream)?|eval/runs|eval/sets/generate)$")
FILE_PATH = re.compile(r"^/api/documents/([0-9a-fA-F-]{36})/file$")


def is_exempt(path: str) -> bool:
    return path in EXEMPT_EXACT or path.startswith(EXEMPT_PREFIX)


class SlidingWindowLimiter:
    """In-memory sliding window. Per-process: use Redis (or a gateway) when running several workers."""

    def __init__(self, limit: int, window: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        if self.limit <= 0:
            return True, 0
        now, q = self.clock(), self.hits[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False, max(1, int(self.window - (now - q[0])) + 1)
        q.append(now)
        if len(self.hits) > 10_000:  # opportunistic cleanup of idle keys
            for k in [k for k, v in self.hits.items() if not v]:
                del self.hits[k]
        return True, 0


def sign_file_token(secret: str, doc_id: str, ttl: int = 300, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    sig = hmac.new(secret.encode(), f"{doc_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify_file_token(secret: str, doc_id: str, token: str, now: float | None = None) -> bool:
    try:
        exp_s, sig = token.split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    if exp < (now if now is not None else time.time()):
        return False
    good = hmac.new(secret.encode(), f"{doc_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(good, sig)


class GuardMiddleware:
    def __init__(self, app, api_keys: list[str] | None = None, rate_limit: int = 0, heavy_limit: int = 0):
        self.app, self.keys = app, api_keys or []
        self.general, self.heavy = SlidingWindowLimiter(rate_limit), SlidingWindowLimiter(heavy_limit)

    def _match_key(self, presented: str) -> str | None:
        for k in self.keys:
            if hmac.compare_digest(k.encode(), presented.encode()):
                return k
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or is_exempt(scope["path"]):
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        h = {k.decode().lower(): v.decode("latin-1") for k, v in scope["headers"]}
        auth = h.get("authorization", "")
        presented = h.get("x-api-key") or (auth[7:] if auth.lower().startswith("bearer ") else "")
        key = self._match_key(presented) if presented else None

        if self.keys and key is None:
            m = FILE_PATH.match(path)
            token = parse_qs(scope.get("query_string", b"").decode()).get("token", [""])[0]
            if not (m and method == "GET" and token and verify_file_token(self.keys[0], m.group(1), token)):
                return await JSONResponse({"detail": "Invalid or missing API key"}, 401, headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)

        client = (scope.get("client") or ("unknown", 0))[0]
        ident = "k:" + hashlib.sha256(key.encode()).hexdigest()[:12] if key else f"ip:{client}"
        checks = ([self.heavy] if method == "POST" and HEAVY.match(path) else []) + [self.general]
        for lim in checks:
            ok, retry = lim.allow(ident)
            if not ok:
                return await JSONResponse({"detail": "Rate limit exceeded. Slow down."}, 429, headers={"Retry-After": str(retry)})(scope, receive, send)
        await self.app(scope, receive, send)


class AccessLogMiddleware:
    """Adds X-Request-ID + Server-Timing (time to first byte) and logs one line per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0 = time.perf_counter()
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode()[:64]
        rid = re.sub(r"[^\w.-]", "", incoming) or uuid.uuid4().hex[:12]
        status = 500

        async def send_wrapper(msg):
            nonlocal status
            if msg["type"] == "http.response.start":
                status = msg["status"]
                ttfb = (time.perf_counter() - t0) * 1000
                msg = {**msg, "headers": [*msg.get("headers", []), (b"x-request-id", rid.encode()), (b"server-timing", f"app;dur={ttfb:.1f}".encode())]}
            await send(msg)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            log.info("%s %s -> %s %.1fms rid=%s", scope["method"], scope["path"], status, (time.perf_counter() - t0) * 1000, rid)
