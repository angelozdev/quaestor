import pytest

from quaestor.domain import errors


def test_errors_form_a_hierarchy():
    for cls in (errors.ValidationError, errors.MissingRate,
                errors.TransferImbalance, errors.NotFound):
        assert issubclass(cls, errors.QuaestorError)


def test_errors_are_raisable():
    with pytest.raises(errors.MissingRate):
        raise errors.MissingRate("fija la tasa usd_cop")
