"""Exception handlers: domain errors -> uniform {"error", "detail"} JSON."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain.errors import (
    CorrectionNotApplied,
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
    CorrectionNotApplied: 409,
    MissingRate: 409,
    TransferImbalance: 409,
    IllegalTransition: 409,
    NotFound: 404,
}


_INTERNAL_ERROR_DETAIL = "Ocurrió un error inesperado. Intenta de nuevo."


def _body(error: str, detail: str) -> dict[str, str]:
    return {"error": error, "detail": detail}


def _domain_body(exc: QuaestorError) -> dict[str, object]:
    body: dict[str, object] = _body(exc.code or type(exc).__name__, str(exc))
    if exc.data:
        body["data"] = exc.data
    return body


_FIELD_ES: dict[str, str] = {
    "category_id": "la categoría",
}

_PYDANTIC_ES: dict[str, str] = {
    "missing": "{field} es un campo requerido",
    "int_parsing": "{field} debe ser un número entero",
    "string_type": "{field} debe ser un texto",
    "decimal_parsing": "{field} debe ser un número válido",
    "greater_than": "{field} debe ser mayor que {gt}",
    "less_than_equal": "{field} debe ser menor o igual que {le}",
    "enum": "{field} debe ser uno de: {expected}",
    "date_from_datetime_parsing": "{field} debe ser una fecha válida",
}


def _spanish_for(err: dict, loc: str) -> str:
    template = _PYDANTIC_ES.get(err["type"])
    if template is None:
        return err.get("msg", "invalid")
    ctx = dict(err.get("ctx") or {})
    ctx.setdefault("field", _FIELD_ES.get(loc, loc))
    return template.format(**ctx)


def _format_validation(exc: RequestValidationError) -> tuple[str, dict[str, str]]:
    parts: list[str] = []
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", ()) if p != "body"]
        loc = ".".join(loc_parts)
        msg = _spanish_for(err, loc)
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
        return JSONResponse(status_code=status, content=_domain_body(exc))

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

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger(__name__).exception(  # noqa: LOG004
            "unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(status_code=500, content=_body("internal_error", _INTERNAL_ERROR_DETAIL))
