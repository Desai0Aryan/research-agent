import logging

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware import AccessLogMiddleware, GuardMiddleware, SlidingWindowLimiter, sign_file_token, verify_file_token

DOC = "11111111-2222-3333-4444-555555555555"


def make(keys=("secret",), rl=0, heavy=0):
    async def ok(request): return PlainTextResponse("ok")
    async def stream(request):
        async def gen():
            for i in range(3):
                yield f"data: {i}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    app = Starlette(routes=[Route("/health", ok), Route("/api/x", ok, methods=["GET", "POST"]), Route("/api/research/stream", stream, methods=["POST"]),
                            Route(f"/api/documents/{DOC}/file", ok)])
    app.add_middleware(GuardMiddleware, api_keys=list(keys), rate_limit=rl, heavy_limit=heavy)
    app.add_middleware(AccessLogMiddleware)
    return TestClient(app)


def test_limiter_window_and_retry_after():
    now = [0.0]
    lim = SlidingWindowLimiter(2, 60, clock=lambda: now[0])
    assert lim.allow("a") == (True, 0) and lim.allow("a") == (True, 0)
    ok, retry = lim.allow("a")
    assert not ok and 1 <= retry <= 61
    assert lim.allow("b")[0]  # keys are independent
    now[0] = 61
    assert lim.allow("a")[0]  # window slid
    assert SlidingWindowLimiter(0).allow("x") == (True, 0)  # 0 = disabled


def test_auth_required_except_health():
    c = make()
    assert c.get("/health").status_code == 200
    r = c.get("/api/x")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert c.get("/api/x", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/api/x", headers={"X-API-Key": "secret"}).status_code == 200
    assert c.get("/api/x", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_auth_disabled_when_no_keys():
    assert make(keys=()).get("/api/x").status_code == 200


def test_signed_file_links_work_only_for_that_file_and_expire():
    tok = sign_file_token("secret", DOC)
    assert verify_file_token("secret", DOC, tok)
    assert not verify_file_token("secret", "other-doc", tok)
    assert not verify_file_token("wrong", DOC, tok)
    assert not verify_file_token("secret", DOC, sign_file_token("secret", DOC, ttl=-10))
    assert not verify_file_token("secret", DOC, "garbage")
    c = make()
    assert c.get(f"/api/documents/{DOC}/file?token={tok}").status_code == 200
    assert c.get(f"/api/documents/{DOC}/file?token=1.bad").status_code == 401
    assert c.get(f"/api/x?token={tok}").status_code == 401  # a file token never unlocks other routes


def test_rate_limits_general_and_heavy_with_429():
    c = make(rl=5, heavy=1)
    h = {"X-API-Key": "secret"}
    assert c.post("/api/research/stream", headers=h).status_code == 200
    r = c.post("/api/research/stream", headers=h)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert c.get("/api/x", headers=h).status_code == 200  # heavy limit doesn't block normal routes
    assert c.get("/health").status_code == 200  # health never limited


def test_sse_streams_through_middleware_and_request_id_header(caplog):
    c = make(keys=())
    with caplog.at_level(logging.INFO, logger="app.access"):
        r = c.post("/api/research/stream", headers={"X-Request-ID": "abc-123"})
    assert r.text == "data: 0\n\ndata: 1\n\ndata: 2\n\n"
    assert r.headers["x-request-id"] == "abc-123" and "dur=" in r.headers["server-timing"]
    assert any("rid=abc-123" in m and "-> 200" in m for m in caplog.messages)
