"""Step handlers — feature 016 error-contract.

AC-1/AC-2/AC-3's ``@backend`` scenarios assert `code`/`data` only, never the
Spanish text — per ADR-0059 the domain exception keeps its original English
message, and Spanish is built entirely on the client from `error-catalog.ts`.
Corrected in CP5 (2026-08-18): the first draft asserted Spanish at this
layer, which would have forced the exception itself to speak Spanish and
leaked into MCP's `domain_error_text` — a surface ADR-0059 promises stays
untouched. See `spec.md`'s "Two streams" section for the full account.

AC-1/AC-2 reuse ``acceptance/handlers/mandatory_categories.py``'s Given/When
steps verbatim (``an expense category "..."``, ``the user tries to record an
expense ... creating the category "..."``, ``the user archives the category
"..."``) and its ``transactions_crud.then_registration_rejected`` /
``_refusal`` helper for ``the registration is rejected`` — this module adds
the code and data Then steps each AC needs.

AC-3 reuses ``transactions_crud.py``'s ``the user registers an expense ...
paying ... in category ...`` and ``movement_corrections.py``'s ``the user
corrects that expense to ... COP`` / ``the correction is rejected``.

AC-4 goes through the real REST boundary (``POST /api/funds``, CSRF-primed
the same way ``recurring_engine._patch_recurring`` does) because the AC is
about Pydantic's own rejection crossing the wire, not a domain refusal — the
missing ``category_id`` is caught by FastAPI's ``RequestValidationError``
handler in ``api/errors.py`` before any service code runs, and that handler
translates Pydantic's `type`/`ctx` to Spanish server-side (a deliberate
exception to the client-side-translation rule, cheaper because Pydantic
hands the code/data split apart for free — see `plan.md` Rebanada 4). The
HTTP layer never raises a Python exception back to the caller, so
``when_submit_fund_with_no_category`` bridges the 4xx response into a
``ValueError`` subclass and routes it through ``World.attempt``, so feature
007's already-registered ``the declaration is rejected``
(``recurring_engine.then_declaration_rejected``, whose accepted types
include plain ``ValueError``) can be reused verbatim instead of colliding
with a second handler for the same literal text.

AC-5 reuses ``fx_read_time.py``'s ``no TRM has been set`` / ``a recorded
expense of ... COP`` / ``the user views the current month's report`` / ``the
report is not shown`` — this module's Then step is a regression guard: it
pins today's raw English ``MissingRate`` text verbatim, because AC-5 is
explicitly about a site 016 does not migrate.
"""

from __future__ import annotations

from quaestor.domain.money import major_to_cents

from . import step
from .fx_read_time import _DEC, _month_str, _rest_client
from .mandatory_categories import _refusal, _refusal_code
from .world import World

CATEGORY_DUPLICATE_ACTIVE_CODE = "category_duplicate_active"
CATEGORY_DUPLICATE_ARCHIVED_CODE = "category_duplicate_archived"
AMOUNT_NOT_POSITIVE_CODE = "amount_not_positive"

_NO_TRM_DETAIL = "no TRM set — set the USD→COP rate (TRM) first"


class ApiRejection(ValueError):
    """A REST call answered 4xx/5xx; carries the JSON body the API returned."""

    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(body.get("detail") or str(body))


@step(
    r"the user submits a fondo with no category, the (?P<rule>fixed) rule,"
    r" and an amount of (?P<amount>" + _DEC + r") (?P<currency>[A-Z]{3})"
)
def when_submit_fund_with_no_category(world: World, rule: str, amount: str, currency: str) -> None:
    def action():
        client, auth = _rest_client(world)
        from quaestor.api.csrf import CSRF_COOKIE, CSRF_HEADER

        client.get("/api/auth/me", headers=auth)
        headers = {**auth, CSRF_HEADER: client.cookies.get(CSRF_COOKIE, "")}
        resp = client.post(
            "/api/funds",
            headers=headers,
            json={
                "rule": rule,
                "start_month": _month_str(world.today),
                "amount": major_to_cents(amount),
            },
        )
        if resp.status_code >= 400:
            raise ApiRejection(resp.status_code, resp.json())
        world.fund_response = resp.json()

    world.attempt(action)


@step(r"the refusal carries a stable code identifying it as a duplicate category")
def then_refusal_code_duplicate_active(world: World) -> None:
    code = _refusal_code(world, "creating an expense category whose name an active one already holds")
    assert code == CATEGORY_DUPLICATE_ACTIVE_CODE, (
        f"expected the refusal to carry the stable code {CATEGORY_DUPLICATE_ACTIVE_CODE!r} identifying "
        f"a duplicate active category, got {code!r} (error: {world.last_error!r})"
    )


@step(
    r"the refusal carries a stable code identifying it as an archived-category duplicate, "
    r"distinct from the code for an active-category duplicate"
)
def then_refusal_code_duplicate_archived(world: World) -> None:
    code = _refusal_code(world, "creating an expense category whose name an archived one already holds")
    assert code == CATEGORY_DUPLICATE_ARCHIVED_CODE and code != CATEGORY_DUPLICATE_ACTIVE_CODE, (
        "expected the refusal to carry a code identifying an archived-category duplicate, distinct from "
        f"AC-1's {CATEGORY_DUPLICATE_ACTIVE_CODE!r} — expected {CATEGORY_DUPLICATE_ARCHIVED_CODE!r}, "
        f"got {code!r} (error: {world.last_error!r})"
    )


@step(r"the refusal carries the category's name and direction as data, not baked into a sentence")
def then_refusal_data_has_name_and_direction(world: World) -> None:
    err = world.last_error
    assert err is not None, "the action succeeded, so there is no refusal to carry data"
    data = getattr(err, "data", None) or {}
    assert data.get("name"), f"expected the refusal's data to carry a non-empty 'name', got {data!r}"
    assert data.get("direction") in ("expense", "income"), (
        f"expected the refusal's data to carry a valid 'direction', got {data!r}"
    )


@step(r"the refusal carries a stable code identifying it as an invalid amount")
def then_refusal_code_amount_not_positive(world: World) -> None:
    code = _refusal_code(world, "correcting a movement to an amount that is not greater than zero")
    assert code == AMOUNT_NOT_POSITIVE_CODE, (
        f"expected the refusal to carry the stable code {AMOUNT_NOT_POSITIVE_CODE!r}, "
        f"got {code!r} (error: {world.last_error!r})"
    )


@step(r"the user is told, in Spanish, that the category is required")
def then_told_spanish_category_required(world: World) -> None:
    message = _refusal(world, "declaring a fund with no category").lower()
    assert "categoría" in message and "requer" in message, (
        f"expected a Spanish message saying the category is required, got: {message!r}"
    )


@step(r"the user is told, in English as before, that no TRM was set")
def then_told_english_no_trm_as_before(world: World) -> None:
    err = world.last_error
    assert err is not None, "no refusal was captured; the report must have been shown"
    message = str(err)
    assert message == _NO_TRM_DETAIL, (
        "AC-5: a site this feature does not migrate must keep answering with today's raw detail, "
        f"unchanged — expected {_NO_TRM_DETAIL!r}, got {message!r}"
    )
