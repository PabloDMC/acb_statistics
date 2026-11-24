"""
Caché en memoria de las respuestas GET.

La base de datos se abre en solo lectura y solo cambia cuando se reconstruye con dbt, y para eso
hay que reiniciar la API (dbt necesita escribir en el fichero). Así que, mientras el proceso vive,
la misma URL devuelve siempre lo mismo: se puede guardar la respuesta entera sin caducidad.
Es la optimización con más efecto por menos código: la segunda visita a cualquier página es
inmediata y el servidor gratuito no repite consultas pesadas (tablas por 100 posesiones, etc.).

Límite por número de respuestas (LRU); los errores y las respuestas grandes no se guardan.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/health")


class ResponseCacheMiddleware:
    def __init__(self, app: ASGIApp, max_entries: int = 4096, max_body_bytes: int = 5_000_000) -> None:
        self.app = app
        self.max_entries = max_entries
        self.max_body_bytes = max_body_bytes
        self._store: OrderedDict[str, tuple[int, list[tuple[bytes, bytes]], bytes]] = OrderedDict()
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "GET" or scope["path"].startswith(_SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        key = scope["path"] + "?" + scope.get("query_string", b"").decode()
        with self._lock:
            cached = self._store.get(key)
            if cached is not None:
                self._store.move_to_end(key)
                self.hits += 1
        if cached is not None:
            status, headers, body = cached
            await send({"type": "http.response.start", "status": status,
                        "headers": headers + [(b"x-cache", b"HIT")]})
            await send({"type": "http.response.body", "body": body})
            return

        self.misses += 1
        start: dict = {}
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                start.update(message)
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)

        body = b"".join(chunks)
        if start.get("status") == 200 and len(body) <= self.max_body_bytes:
            headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
            headers.append((b"content-length", str(len(body)).encode()))
            with self._lock:
                self._store[key] = (200, headers, body)
                self._store.move_to_end(key)
                while len(self._store) > self.max_entries:
                    self._store.popitem(last=False)
