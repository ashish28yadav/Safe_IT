"""Request boundary limits for untrusted incident ingestion payloads."""

from __future__ import annotations

from starlette.responses import JSONResponse


class IncidentPayloadLimitMiddleware:
    """Reject incident POST bodies larger than the configured byte budget."""

    def __init__(self, app: object, max_bytes: int = 64_000) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if (scope.get("type") != "http" or scope.get("path") != "/api/v1/incidents"
                or scope.get("method") != "POST"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await JSONResponse(status_code=413, content={
                        "detail": f"Incident payload exceeds the {self.max_bytes} byte limit"
                    })(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})(
                    scope, receive, send
                )
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse(status_code=413, content={
                    "detail": f"Incident payload exceeds the {self.max_bytes} byte limit"
                })(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        sent = False

        async def replay_receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)
