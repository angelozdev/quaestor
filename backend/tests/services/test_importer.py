from quaestor.services import importer

HEADER = "date,type,payee,amount,currency,account,category,tags,notes"


def test_empty_csv_is_global_error(session):
    res = importer.import_csv(session, "")
    assert res.ok is False and res.inserted == 0
    assert res.errors and res.errors[0].line == 1


def test_wrong_header_is_global_error(session):
    res = importer.import_csv(session, "date,amount\n2026-06-01,100")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1
    assert "header" in res.errors[0].reason.lower()


def test_header_only_is_global_error(session):
    res = importer.import_csv(session, HEADER + "\n")
    assert res.ok is False and res.inserted == 0
    assert res.errors[0].line == 1


def test_dry_run_flag_is_echoed_on_global_error(session):
    res = importer.import_csv(session, "", dry_run=True)
    assert res.dry_run is True and res.ok is False
