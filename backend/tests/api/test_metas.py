"""The metas REST surface, and the link a purchase carries to one.

The router owns no rule — every refusal here already lives in
`services.metas` or `services.transactions`. What these pin is that the
wire reaches those rules at all: before this, a meta could be linked from
the services layer and from nowhere a browser could reach.
"""

import pytest

from tests.support.fx import set_trm

MONTH = {"month": "2026-08"}


@pytest.fixture(autouse=True)
def a_rate(client, auth):
    """Every read path demands a rate on entry and never guesses one (ADR-0031)."""
    set_trm(client, auth)


def _meta(client, auth, name="Celular", amount=800_000_000, target="2026-12", **extra):
    resp = client.post(
        "/api/metas",
        headers=auth,
        params=MONTH,
        json={"name": name, "amount": amount, "target_month": target, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def account(client, auth):
    return client.post(
        "/api/accounts",
        headers=auth,
        json={"name": "Bank", "type": "debit", "currency": "COP"},
    ).json()


def _expense(client, auth, account, category, amount=800_000_000, **extra):
    return client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "expense",
            "category_id": category,
            "account_id": account["id"],
            "amount": amount,
            "currency": "COP",
            "date": "2026-08-15",
            "payee": "Store",
            **extra,
        },
    )


def test_metas_requires_auth(client):
    assert client.get("/api/metas", params=MONTH).status_code == 401


def test_a_created_meta_is_listed_with_what_it_asks(client, auth):
    _meta(client, auth)
    rows = client.get("/api/metas", headers=auth, params=MONTH).json()
    assert [row["name"] for row in rows] == ["Celular"]
    assert rows[0]["asks"] == 160_000_000
    assert rows[0]["holds"] == 160_000_000


def test_the_preview_says_what_the_meta_would_ask_before_it_exists(client, auth):
    resp = client.post(
        "/api/metas/preview",
        headers=auth,
        params=MONTH,
        json={"name": "Celular", "amount": 800_000_000, "target_month": "2026-12"},
    )
    assert resp.json()["asks"] == 160_000_000
    assert client.get("/api/metas", headers=auth, params=MONTH).json() == []


def test_a_cancelled_meta_leaves_the_list_and_comes_back_with_nothing(client, auth):
    later = {"month": "2026-09"}
    meta = _meta(client, auth)
    client.post(f"/api/metas/{meta['id']}/contributions", headers=auth, params=MONTH, json={"amount": 50_000_000})
    assert client.delete(f"/api/metas/{meta['id']}", headers=auth, params=MONTH).status_code == 204
    assert client.get("/api/metas", headers=auth, params=MONTH).json() == []

    client.post(f"/api/metas/{meta['id']}/restore", headers=auth, params=later)
    restored = client.get("/api/metas", headers=auth, params=later).json()
    assert [row["name"] for row in restored] == ["Celular"]
    assert restored[0]["holds"] == 200_000_000


def test_a_contribution_is_listed_and_can_be_taken_back(client, auth):
    meta = _meta(client, auth)
    made = client.post(
        f"/api/metas/{meta['id']}/contributions",
        headers=auth,
        params=MONTH,
        json={"amount": 50_000_000},
    )
    assert made.status_code == 201
    assert [c["amount"] for c in client.get(f"/api/metas/{meta['id']}/contributions", headers=auth).json()] == [
        50_000_000
    ]

    client.delete(f"/api/metas/contributions/{made.json()['id']}", headers=auth)
    assert client.get(f"/api/metas/{meta['id']}/contributions", headers=auth).json() == []


def test_the_split_names_what_the_month_consumed_and_what_it_saved(client, auth):
    _meta(client, auth)
    split = client.get("/api/metas/split", headers=auth, params=MONTH).json()
    assert split["ahorro"] == 160_000_000
    assert split["year_month"] == "2026-08"


def test_the_available_breakdown_names_the_metas_and_adds_up(client, auth, account, income_category):
    client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": account["id"],
            "amount": 500_000_000,
            "currency": "COP",
            "date": "2026-08-05",
            "payee": "Empresa",
        },
    )
    meta = _meta(client, auth)
    client.post(f"/api/metas/{meta['id']}/contributions", headers=auth, params=MONTH, json={"amount": 50_000_000})

    breakdown = client.get("/api/funds/available", headers=auth, params=MONTH).json()
    assert [row["name"] for row in breakdown["metas"]] == ["Celular"]
    assert breakdown["metas"][0]["asks"] == 160_000_000
    assert breakdown["contributed"] == 50_000_000
    assert breakdown["released"] == 0

    claimed = (
        sum(fund["asks"] for fund in breakdown["funds"])
        + sum(meta["asks"] for meta in breakdown["metas"])
        + breakdown["contributed"]
        - breakdown["released"]
    )
    assert breakdown["income"] - claimed - breakdown["uncovered"] == breakdown["free"]


def test_an_expense_reaches_the_meta_through_the_wire(client, auth, account, expense_category):
    meta = _meta(client, auth)
    created = _expense(client, auth, account, expense_category, meta_id=meta["id"])
    assert created.status_code == 201
    assert created.json()["meta_id"] == meta["id"]
    assert client.get("/api/metas", headers=auth, params=MONTH).json()[0]["complete"] is True


def test_money_coming_in_is_refused_a_meta_through_the_wire(client, auth, account, income_category):
    meta = _meta(client, auth)
    resp = client.post(
        "/api/transactions",
        headers=auth,
        json={
            "type": "income",
            "category_id": income_category,
            "account_id": account["id"],
            "amount": 800_000_000,
            "currency": "COP",
            "date": "2026-08-15",
            "payee": "Empresa",
            "meta_id": meta["id"],
        },
    )
    assert resp.status_code == 422
    assert "only money going out" in resp.text


def test_a_cancelled_meta_takes_no_link_through_the_wire(client, auth, account, expense_category):
    meta = _meta(client, auth)
    client.delete(f"/api/metas/{meta['id']}", headers=auth, params=MONTH)
    resp = _expense(client, auth, account, expense_category, meta_id=meta["id"])
    assert resp.status_code == 422
    assert "was cancelled" in resp.text


def test_the_link_can_be_removed_and_moved_through_the_wire(client, auth, account, expense_category):
    celular = _meta(client, auth)
    televisor = _meta(client, auth, name="Televisor", amount=500_000_000)
    tx = _expense(client, auth, account, expense_category, meta_id=celular["id"]).json()

    moved = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"meta_id": televisor["id"]})
    assert moved.json()["meta_id"] == televisor["id"]

    unlinked = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"meta_id": None})
    assert unlinked.json()["meta_id"] is None


def test_an_edit_that_never_mentions_the_meta_leaves_the_link_alone(client, auth, account, expense_category):
    meta = _meta(client, auth)
    tx = _expense(client, auth, account, expense_category, meta_id=meta["id"]).json()
    edited = client.patch(f"/api/transactions/{tx['id']}", headers=auth, json={"payee": "Otra tienda"})
    assert edited.json()["meta_id"] == meta["id"]
