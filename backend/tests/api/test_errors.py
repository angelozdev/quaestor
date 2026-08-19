import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from quaestor.api.errors import Unauthorized, _spanish_for, register_exception_handlers
from quaestor.domain.errors import (
    CorrectionNotApplied,
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)


class _UnexpectedBug(RuntimeError):
    """A bug nobody predicted, distinct from every QuaestorError subclass."""


class _UnmappedQuaestorError(QuaestorError):
    """A domain error deliberately absent from `_STATUS`, to prove its default holds."""


@pytest.fixture
def error_client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/{kind}")
    def boom(kind: str):
        mapping = {
            "validation": ValidationError("bad amount"),
            "rate": MissingRate("set usd_cop rate for 2026-06-17"),
            "imbalance": TransferImbalance("does not balance"),
            "notfound": NotFound("account 9 not found"),
            "auth": Unauthorized("credentials required or invalid"),
            "unexpected": _UnexpectedBug("division by zero at line 42"),
            "correction": CorrectionNotApplied("balance did not move by the declared delta"),
            "unmapped": _UnmappedQuaestorError("a future domain error nobody mapped yet"),
        }
        raise mapping[kind]

    @app.get("/needs-int")
    def needs_int(n: int):  # triggers RequestValidationError on ?n=abc
        return {"n": n}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "kind,status,error",
    [
        ("validation", 422, "ValidationError"),
        ("rate", 409, "MissingRate"),
        ("imbalance", 409, "TransferImbalance"),
        ("notfound", 404, "NotFound"),
        ("auth", 401, "Unauthorized"),
        ("correction", 409, "CorrectionNotApplied"),
    ],
)
def test_domain_errors_map_to_uniform_json(error_client, kind, status, error):
    resp = error_client.get(f"/boom/{kind}")
    assert resp.status_code == status
    body = resp.json()
    assert body["error"] == error
    assert isinstance(body["detail"], str) and body["detail"]


def test_a_domain_error_absent_from_status_defaults_to_422(error_client):
    resp = error_client.get("/boom/unmapped")
    assert resp.status_code == 422
    assert resp.json()["error"] == "_UnmappedQuaestorError"


def test_request_validation_error_is_422_uniform(error_client):
    resp = error_client.get("/needs-int", params={"n": "abc"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "ValidationError"
    assert isinstance(body["detail"], str)


def test_unexpected_exception_answers_with_a_fixed_spanish_code_and_message(error_client, caplog):
    with caplog.at_level(logging.ERROR, logger="quaestor.api.errors"):
        resp = error_client.get("/boom/unexpected")

    assert resp.status_code == 500
    assert resp.json() == {
        "error": "internal_error",
        "detail": "Ocurrió un error inesperado. Intenta de nuevo.",
    }


def test_unexpected_exception_is_logged_but_never_reaches_the_client(error_client, caplog):
    with caplog.at_level(logging.ERROR, logger="quaestor.api.errors"):
        resp = error_client.get("/boom/unexpected")

    assert "division by zero at line 42" not in resp.text
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "unhandled error on GET /boom/unexpected" in logged
    assert any(record.exc_info for record in caplog.records), "the real exception must be logged with a traceback"
    assert "_UnexpectedBug" in caplog.text
    assert "division by zero at line 42" in caplog.text


def test_missing_names_the_known_field_in_spanish():
    err = {"type": "missing", "msg": "Field required", "ctx": None}
    message = _spanish_for(err, "category_id").lower()
    assert "categoría" in message
    assert "requer" in message


def test_missing_falls_back_to_the_raw_field_name_when_unmapped():
    err = {"type": "missing", "msg": "Field required", "ctx": None}
    assert _spanish_for(err, "payee") == "payee es un campo requerido"


def test_int_parsing_is_spanish():
    err = {"type": "int_parsing", "msg": "Input should be a valid integer", "ctx": None}
    assert _spanish_for(err, "amount") == "amount debe ser un número entero"


def test_string_type_is_spanish():
    err = {"type": "string_type", "msg": "Input should be a valid string", "ctx": None}
    assert _spanish_for(err, "name") == "name debe ser un texto"


def test_decimal_parsing_is_spanish():
    err = {"type": "decimal_parsing", "msg": "Input should be a valid decimal", "ctx": None}
    assert _spanish_for(err, "usd_cop") == "usd_cop debe ser un número válido"


def test_greater_than_interpolates_the_bound():
    err = {"type": "greater_than", "msg": "Input should be greater than 0", "ctx": {"gt": 0}}
    assert _spanish_for(err, "amount") == "amount debe ser mayor que 0"


def test_less_than_equal_interpolates_the_bound():
    err = {"type": "less_than_equal", "msg": "Input should be <= 1000", "ctx": {"le": 1000}}
    assert _spanish_for(err, "interval_count") == "interval_count debe ser menor o igual que 1000"


def test_enum_interpolates_the_allowed_values():
    err = {
        "type": "enum",
        "msg": "Input should be 'fixed', 'average' or 'from-recurring'",
        "ctx": {"expected": "'fixed', 'average' or 'from-recurring'"},
    }
    assert _spanish_for(err, "rule") == "rule debe ser uno de: 'fixed', 'average' or 'from-recurring'"


def test_date_from_datetime_parsing_is_spanish():
    err = {
        "type": "date_from_datetime_parsing",
        "msg": "Input should be a valid date, invalid character in year",
        "ctx": {"error": "invalid character in year"},
    }
    assert _spanish_for(err, "start_date") == "start_date debe ser una fecha válida"


def test_unknown_type_falls_back_to_pydantics_own_english_message():
    err = {"type": "some_new_pydantic_type_2027", "msg": "a brand new kind of rejection", "ctx": None}
    assert _spanish_for(err, "whatever") == "a brand new kind of rejection"
