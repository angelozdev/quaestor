from sqlmodel import SQLModel

from quaestor.domain import models


def test_all_tables_registered():
    names = set(SQLModel.metadata.tables.keys())
    assert {
        "account", "category_group", "category", "transaction",
        "tag", "transaction_tag", "settings",
    } <= names
    assert "fx_rate" not in names


def test_transaction_has_required_columns():
    cols = set(SQLModel.metadata.tables["transaction"].columns.keys())
    assert {
        "id", "date", "payee", "notes", "type", "status", "amount",
        "currency", "account_id", "category_id",
        "transfer_group_id", "source", "created_at",
    } <= cols
    assert "fx_rate" not in cols
    assert "to_base" not in cols


def test_enums_have_expected_members():
    assert models.AccountType.credit.value == "credit"
    assert models.TxType.transfer.value == "transfer"
    assert models.TxStatus.posted.value == "posted"
    assert models.Source.import_.value == "import"
