import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quaestor.api.errors import Unauthorized, register_exception_handlers
from quaestor.domain.errors import (
    MissingRate,
    NotFound,
    TransferImbalance,
    ValidationError,
)


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
            "auth": Unauthorized("credenciales requeridas o inválidas"),
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
    ],
)
def test_domain_errors_map_to_uniform_json(error_client, kind, status, error):
    resp = error_client.get(f"/boom/{kind}")
    assert resp.status_code == status
    body = resp.json()
    assert body["error"] == error
    assert isinstance(body["detail"], str) and body["detail"]


def test_request_validation_error_is_422_uniform(error_client):
    resp = error_client.get("/needs-int", params={"n": "abc"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "ValidationError"
    assert isinstance(body["detail"], str)
