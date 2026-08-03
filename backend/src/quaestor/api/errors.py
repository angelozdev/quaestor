"""Exception handlers: domain errors -> uniform {"error", "detail"} JSON."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain.errors import (
    IllegalTransition,
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)


class Unauthorized(Exception):
    """Auth missing or invalid (API layer; not a domain error)."""

    def __init__(self, detail: str = "credentials required or invalid") -> None:
        self.detail = detail
        super().__init__(detail)


_STATUS: dict[type[QuaestorError], int] = {
    ValidationError: 422,
    MissingRate: 409,
    TransferImbalance: 409,
    IllegalTransition: 409,
    NotFound: 404,
}


def _body(error: str, detail: str) -> dict[str, str]:
    return {"error": error, "detail": detail}


def _format_validation(exc: RequestValidationError) -> tuple[str, dict[str, str]]:
    parts: list[str] = []
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", ()) if p != "body"]
        loc = ".".join(loc_parts)
        msg = err.get("msg", "invalid")
        if loc:
            fields[loc] = msg
            parts.append(f"{loc}: {msg}".strip(": "))
        else:
            parts.append(msg)
    return ("; ".join(parts) or "invalid request body"), fields


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(QuaestorError)
    async def _domain(request: Request, exc: QuaestorError) -> JSONResponse:
        status = _STATUS.get(type(exc), 422)
        return JSONResponse(status_code=status, content=_body(type(exc).__name__, str(exc)))

    @app.exception_handler(Unauthorized)
    async def _auth(request: Request, exc: Unauthorized) -> JSONResponse:
        return JSONResponse(status_code=401, content=_body("Unauthorized", exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        detail, fields = _format_validation(exc)
        return JSONResponse(
            status_code=422,
            content={"error": "ValidationError", "detail": detail, "fields": fields},
        )
