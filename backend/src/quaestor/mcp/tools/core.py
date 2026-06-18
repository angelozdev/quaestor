"""MCP core tools: parse input, resolve names, call ONE service, format output.

No domain logic lives here. Each public impl is wrapped by ``_as_text``, so a
typed domain error becomes agent text instead of an exception. Impls take a
``Session`` (one per request, opened by the registry wrapper) plus a validated
Pydantic input model.
"""
from __future__ import annotations

import functools
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from ...domain.errors import NotFound, QuaestorError
from ...domain.models import Account, Category
from ...services import accounts, categories, fx, tags, transactions
from .. import format


# ----- input models (one per tool; the SDK publishes their JSON Schema) -----


class RegistrarGastoInput(BaseModel):
    payee: str = Field(description="Comercio o beneficiario, ej. 'Mercado'")
    amount: int = Field(
        gt=0, description="Monto en centavos, moneda original (40 mil COP = 4000000)"
    )
    account: str = Field(description="Nombre de la cuenta, ej. 'Bancolombia'")
    currency: str = Field(default="COP", description="Moneda ISO; por defecto COP")
    category: str | None = Field(default=None, description="Nombre de la categoría (opcional)")
    date: Date | None = Field(default=None, description="Fecha YYYY-MM-DD; por defecto hoy")
    tags: list[str] = Field(default_factory=list, description="Etiquetas por nombre")
    notes: str | None = Field(default=None, description="Notas libres (opcional)")


class RegistrarIngresoInput(BaseModel):
    payee: str = Field(description="Fuente del ingreso, ej. 'Sueldo'")
    amount: int = Field(gt=0, description="Monto en centavos, moneda original")
    account: str = Field(description="Nombre de la cuenta destino")
    currency: str = Field(default="COP", description="Moneda ISO; por defecto COP")
    category: str | None = Field(default=None, description="Nombre de la categoría (opcional)")
    date: Date | None = Field(default=None, description="Fecha YYYY-MM-DD; por defecto hoy")
    tags: list[str] = Field(default_factory=list, description="Etiquetas por nombre")
    notes: str | None = Field(default=None, description="Notas libres (opcional)")


class TransferirInput(BaseModel):
    from_account: str = Field(description="Cuenta origen (por nombre)")
    to_account: str = Field(description="Cuenta destino (por nombre)")
    amount: int = Field(gt=0, description="Monto en centavos")
    currency: str = Field(default="COP", description="Moneda; debe coincidir con ambas cuentas")
    date: Date | None = Field(default=None, description="Fecha YYYY-MM-DD; por defecto hoy")
    notes: str | None = Field(default=None, description="Notas libres (opcional)")


class FijarTasaInput(BaseModel):
    date: Date = Field(description="Fecha de la tasa, YYYY-MM-DD")
    usd_cop: float = Field(gt=0, description="Pesos por dólar, ej. 4150")


class ConsultarTasaInput(BaseModel):
    date: Date | None = Field(default=None, description="Fecha YYYY-MM-DD; por defecto hoy")


class ConsultarTxInput(BaseModel):
    desde: Date | None = Field(default=None, description="Incluir desde esta fecha")
    hasta: Date | None = Field(default=None, description="Incluir hasta esta fecha")
    account: str | None = Field(default=None, description="Filtrar por cuenta (nombre)")
    category: str | None = Field(default=None, description="Filtrar por categoría (nombre)")
    tag: str | None = Field(default=None, description="Filtrar por etiqueta (nombre)")
    type: Literal["expense", "income", "transfer"] | None = Field(
        default=None, description="Tipo de transacción"
    )
    status: Literal["posted", "planned"] | None = Field(
        default=None, description="Estado de la transacción"
    )


# ----- error-to-text wrapper -----


def _as_text(fn):
    """Wrap an impl so typed domain errors become agent text, not exceptions."""

    @functools.wraps(fn)
    def wrapper(session: Session, *args):
        try:
            return fn(session, *args)
        except QuaestorError as exc:
            return format.domain_error_text(exc)

    return wrapper


# ----- name resolution (agent speaks names; services speak ids) -----


def _resolve_account(session: Session, name: str) -> Account:
    all_accounts = accounts.list_accounts(session)
    target = name.strip().lower()
    for account in all_accounts:
        if account.name.lower() == target:
            return account
    available = ", ".join(a.name for a in all_accounts) or "(ninguna)"
    raise NotFound(f"No encontré la cuenta '{name}'. Cuentas: {available}.")


def _resolve_category(session: Session, name: str) -> Category:
    target = name.strip().lower()
    for category in categories.list_categories(session):
        if category.name.lower() == target:
            return category
    raise NotFound(
        f"No encontré la categoría '{name}'. Puedes crearla o registrar sin categoría."
    )


# ----- write tools -----


@_as_text
def registrar_gasto(session: Session, inp: RegistrarGastoInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = transactions.record_expense(
        session,
        account_id=account.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        payee=inp.payee,
        category_id=category.id if category else None,
        notes=inp.notes,
        source="agent",
    )
    if inp.tags:
        tags.tag_transaction(session, tx.id, inp.tags)
    account = accounts.get_account(session, account.id)
    return format.expense_confirmation(tx, account)


@_as_text
def registrar_ingreso(session: Session, inp: RegistrarIngresoInput) -> str:
    account = _resolve_account(session, inp.account)
    category = _resolve_category(session, inp.category) if inp.category else None
    tx = transactions.record_income(
        session,
        account_id=account.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        payee=inp.payee,
        category_id=category.id if category else None,
        notes=inp.notes,
        source="agent",
    )
    if inp.tags:
        tags.tag_transaction(session, tx.id, inp.tags)
    account = accounts.get_account(session, account.id)
    return format.income_confirmation(tx, account)


@_as_text
def transferir(session: Session, inp: TransferirInput) -> str:
    src = _resolve_account(session, inp.from_account)
    dst = _resolve_account(session, inp.to_account)
    transactions.transfer(
        session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=inp.amount,
        currency=inp.currency,
        date=inp.date or Date.today(),
        notes=inp.notes,
        source="agent",
    )
    src = accounts.get_account(session, src.id)
    dst = accounts.get_account(session, dst.id)
    return format.transfer_confirmation(src, dst, inp.amount, inp.currency)


@_as_text
def fijar_tasa_fx(session: Session, inp: FijarTasaInput) -> str:
    fr = fx.set_fx_rate(session, inp.date, inp.usd_cop)
    return format.fx_set(fr)
