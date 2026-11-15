"""Test isolation of per-coordinator price values."""

from custom_components.pun_sensor.interfaces import Fascia, PunValues


def test_price_values_are_not_shared_between_instances():
    """Reloaded coordinators must not inherit a mutable class-level cache."""
    first = PunValues()
    second = PunValues()
    first.value[Fascia.MONO] = 0.42
    assert second.value[Fascia.MONO] == 0.0
    assert first.value is not second.value
