"""Excepciones de dominio, desacopladas de FastAPI/HTTP."""

from fastapi import Request
from fastapi.responses import JSONResponse


class ResourceNotFoundError(Exception):
    def __init__(self, resource: str, identifier: object):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} con id={identifier!r} no encontrado")


def register_exception_handlers(app) -> None:
    @app.exception_handler(ResourceNotFoundError)
    async def _not_found_handler(request: Request, exc: ResourceNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "resource": exc.resource},
        )
