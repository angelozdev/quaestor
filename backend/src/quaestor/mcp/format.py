"""Render service results and domain errors to agent-friendly markdown.

This module is named `format` (per the P2 spec) and shadows the builtin
`format()` for importers; do not call the builtin here.
"""
from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

from ..domain.errors import (
    MissingRate,
    NotFound,
    QuaestorError,
    TransferImbalance,
    ValidationError,
)
from ..domain.models import (
    Account,
    Category,
    CategoryGroup,
    FxRate,
    Tag,
    Transaction,
)
from ..domain.money import cents_to_major


def money(cents: int, currency: str) -> str:
    """Render integer cents as major units + currency, e.g. '40000.00 COP'."""
    return f"{cents_to_major(cents)} {currency}"


def domain_error_text(exc: QuaestorError) -> str:
    """Translate a typed domain error into clear agent text (never a stack trace)."""
    if isinstance(exc, MissingRate):
        return (
            "No tengo la tasa USD→COP para esa fecha. "
            "Fíjala con `fijar_tasa_fx` (date, usd_cop) y reintento."
        )
    if isinstance(exc, TransferImbalance):
        return f"No pude registrar la transferencia: {exc}."
    if isinstance(exc, NotFound):
        # Resolution helpers already raise NotFound with Spanish guidance.
        return str(exc)
    if isinstance(exc, ValidationError):
        return f"Entrada inválida: {exc}."
    return f"Error: {exc}."


def _confirmation(verb: str, tx: Transaction, account: Account) -> str:
    lines = [
        f"✅ {verb}: **{tx.payee}** — {money(tx.amount, tx.currency)}",
        f"- Cuenta: {account.name} "
        f"(nuevo balance: {money(account.balance, account.currency)})",
    ]
    if tx.currency != "COP":
        lines.append(f"- Equivalente: {money(tx.to_base, 'COP')}")
    return "\n".join(lines)


def expense_confirmation(tx: Transaction, account: Account) -> str:
    return _confirmation("Gasto registrado", tx, account)


def income_confirmation(tx: Transaction, account: Account) -> str:
    return _confirmation("Ingreso registrado", tx, account)


def transfer_confirmation(
    src: Account, dst: Account, amount: int, currency: str
) -> str:
    return "\n".join(
        [
            f"✅ Transferencia: {money(amount, currency)} "
            f"de **{src.name}** a **{dst.name}**",
            f"- {src.name}: {money(src.balance, src.currency)}",
            f"- {dst.name}: {money(dst.balance, dst.currency)}",
        ]
    )


def fx_set(fr: FxRate) -> str:
    # Strip trailing zeros while preserving significant digits
    rate_str = str(fr.usd_cop) if fr.usd_cop % 1 else str(fr.usd_cop.to_integral_value())
    return f"✅ Tasa USD→COP para {fr.date.isoformat()}: {rate_str}"


def fx_current(rate, on: Date) -> str:
    if isinstance(rate, str):
        rate_str = rate
    else:
        d = Decimal(str(rate)) if not isinstance(rate, Decimal) else rate
        rate_str = str(d) if d % 1 else str(d.to_integral_value())
    return f"Tasa vigente USD→COP al {on.isoformat()}: {rate_str}"


def accounts_table(accounts: list[Account]) -> str:
    if not accounts:
        return "No hay cuentas."
    rows = ["| Cuenta | Tipo | Balance | Moneda |", "|---|---|---|---|"]
    for a in accounts:
        rows.append(
            f"| {a.name} | {a.type.value} | {cents_to_major(a.balance)} | {a.currency} |"
        )
    return "\n".join(rows)


def categories_table(categories: list[Category], groups: list[CategoryGroup]) -> str:
    if not categories:
        return "No hay categorías."
    group_name = {g.id: g.name for g in groups}
    rows = ["| Categoría | Grupo | Ingreso |", "|---|---|---|"]
    for c in categories:
        group = group_name.get(c.group_id, "—") if c.group_id else "—"
        rows.append(f"| {c.name} | {group} | {'sí' if c.is_income else 'no'} |")
    return "\n".join(rows)


def tags_list(tags: list[Tag]) -> str:
    if not tags:
        return "No hay etiquetas."
    return "Etiquetas: " + ", ".join(t.name for t in tags)


def transactions_table(txs: list[Transaction]) -> str:
    if not txs:
        return "No hay transacciones para esos filtros."
    rows = [
        "| Fecha | Tipo | Beneficiario | Monto | Moneda | COP |",
        "|---|---|---|---|---|---|",
    ]
    total = 0
    for t in txs:
        total += t.to_base
        rows.append(
            f"| {t.date.isoformat()} | {t.type.value} | {t.payee} | "
            f"{cents_to_major(t.amount)} | {t.currency} | {cents_to_major(t.to_base)} |"
        )
    rows.append("")
    rows.append(f"**Total (COP): {cents_to_major(total)}** · {len(txs)} transacción(es)")
    return "\n".join(rows)
