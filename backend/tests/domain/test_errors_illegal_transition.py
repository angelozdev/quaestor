from quaestor.api.errors import _STATUS
from quaestor.domain.errors import IllegalTransition, QuaestorError


def test_illegal_transition_is_a_domain_error():
    assert issubclass(IllegalTransition, QuaestorError)


def test_illegal_transition_maps_to_409():
    assert _STATUS[IllegalTransition] == 409
