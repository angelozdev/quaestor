"""Step handlers — feature 017 transaction-filters-and-drilldown.

Only the ``@backend`` scenarios bind here; the mixed stream's untagged
scenarios (filter bar shape, drill-down navigation) pin what the owner sees
on screen and bind to vitest instead, per ``spec.md``'s header.

Amount-range and group filtering are new vocabulary this feature added:
``services.transactions.list_transactions`` gained ``amount_min``/
``amount_max``/``group_id``, and the MCP ``ListTransactionsInput`` gained
the same pair plus ``group`` (by name). Every step below calls those real
functions — through ``world.attempt`` where the call can fail — never a
stand-in.

The app-side/assistant-side pairs (AC-7) mirror
``transactions_crud.py``'s tag-parity steps exactly: the app half goes
through the REST ``TestClient`` (``_rest_client``), the assistant half
through the MCP tools layer directly, never through the service call both
of those wrap.
"""

from __future__ import annotations

from quaestor.domain.money import major_to_cents
from quaestor.services import categories, transactions

from . import step
from .fx_read_time import _DEC, _rest_client
from .transactions_crud import _MCP_TABLE_ROW
from .world import World

# ------------------------------------------------------------------- Given


@step(r'a category group "(?P<name>[^"]+)"')
def given_category_group(world: World, name: str) -> None:
    group = categories.create_group(world.session, name)
    world.groups[name] = group.id


@step(r'a category "(?P<name>[^"]+)" in group "(?P<group>[^"]+)"')
def given_category_in_group(world: World, name: str, group: str) -> None:
    cat = categories.create_category(world.session, name, group_id=world.groups[group])
    world.categories[name] = cat.id


# -------------------------------------------------------------------- When


def _list_by_amount(world: World, amount_min: str | None, amount_max: str | None) -> None:
    world.filtered_rows = None

    def action():
        kwargs = {}
        if amount_min is not None:
            kwargs["amount_min"] = major_to_cents(amount_min)
        if amount_max is not None:
            kwargs["amount_max"] = major_to_cents(amount_max)
        world.filtered_rows = transactions.list_transactions(world.session, **kwargs)

    world.attempt(action)


@step(
    r"the user lists transactions with amount between "
    r"(?P<amount_min>" + _DEC + r") and (?P<amount_max>" + _DEC + r") COP"
)
def when_list_by_amount_range(world: World, amount_min: str, amount_max: str) -> None:
    _list_by_amount(world, amount_min, amount_max)


@step(r"the user lists transactions with amount at least (?P<amount_min>" + _DEC + r") COP")
def when_list_by_amount_min(world: World, amount_min: str) -> None:
    _list_by_amount(world, amount_min, None)


@step(r"the user lists transactions with amount at most (?P<amount_max>" + _DEC + r") COP")
def when_list_by_amount_max(world: World, amount_max: str) -> None:
    _list_by_amount(world, None, amount_max)


@step(r'the user lists transactions in group "(?P<group>[^"]+)"(?: in category "(?P<category>[^"]+)")?')
def when_list_by_group(world: World, group: str, category: str | None) -> None:
    world.filtered_rows = None

    def action():
        kwargs = {"group_id": world.groups[group]}
        if category is not None:
            kwargs["category_id"] = world.categories[category]
        world.filtered_rows = transactions.list_transactions(world.session, **kwargs)

    world.attempt(action)


@step(r"the user lists transactions with amount at least (?P<amount_min>" + _DEC + r") COP in the app")
def when_app_lists_by_amount_min(world: World, amount_min: str) -> None:
    def action():
        client, auth = _rest_client(world)
        resp = client.get("/api/transactions", params={"amount_min": major_to_cents(amount_min)}, headers=auth)
        if resp.status_code != 200:
            raise AssertionError(f"GET /api/transactions?amount_min={amount_min} -> {resp.status_code}: {resp.text}")
        world.app_payees = sorted(row["payee"] for row in resp.json())

    world.attempt(action)


@step(r'the user lists transactions in group "(?P<group>[^"]+)" in the app')
def when_app_lists_by_group(world: World, group: str) -> None:
    def action():
        group_id = world.groups[group]
        client, auth = _rest_client(world)
        resp = client.get("/api/transactions", params={"group_id": group_id}, headers=auth)
        if resp.status_code != 200:
            raise AssertionError(f"GET /api/transactions?group_id={group_id} -> {resp.status_code}: {resp.text}")
        world.app_payees = sorted(row["payee"] for row in resp.json())

    world.attempt(action)


def _assistant_payees_from(text: str) -> list[str]:
    matches = [m for m in (_MCP_TABLE_ROW.match(line) for line in text.splitlines()) if m is not None]
    return sorted(m.group("payee").strip() for m in matches if m.group("type").strip() != "Type")


@step(r"the assistant lists transactions with amount at least (?P<amount_min>" + _DEC + r") COP")
def when_assistant_lists_by_amount_min(world: World, amount_min: str) -> None:
    def action():
        from quaestor.mcp.tools import core as mcp_core

        text = mcp_core.list_transactions(
            world.session, mcp_core.ListTransactionsInput(amount_min=major_to_cents(amount_min))
        )
        world.assistant_payees = _assistant_payees_from(text)

    world.attempt(action)


@step(r'the assistant lists transactions in group "(?P<group>[^"]+)"')
def when_assistant_lists_by_group(world: World, group: str) -> None:
    def action():
        from quaestor.mcp.tools import core as mcp_core

        text = mcp_core.list_transactions(world.session, mcp_core.ListTransactionsInput(group=group))
        world.assistant_payees = _assistant_payees_from(text)

    world.attempt(action)


# -------------------------------------------------------------------- Then


@step(r"the list is empty")
def then_list_is_empty(world: World) -> None:
    world.require_clean("listing should have succeeded")
    assert world.filtered_rows is not None, "no filtered list was produced"
    payees = [tx.payee for tx in world.filtered_rows]
    assert payees == [], f"expected an empty list, got {payees}"
