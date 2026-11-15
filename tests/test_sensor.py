"""Verify freshness and restore behaviour through HA's state machine."""

from datetime import date
import re

import pytest
from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from custom_components.pun_sensor.const import DOMAIN
from homeassistant.core import State
from homeassistant.setup import async_setup_component

GME_URL = re.compile(r"https://gme\.mercatoelettrico\.org/.*")


@pytest.mark.parametrize(
    ("saved_date", "saved_band", "expected"),
    [
        (None, "F1", "unavailable"),
        ("2026-11-11", "F1", "unavailable"),
        ("2026-11-12", "F1", "0.1"),
        ("2026-11-12", "F3", "unavailable"),
    ],
)
async def test_restored_current_band_is_dated_and_matches_band(
    *, hass, config_entry, freezer, saved_date, saved_band, expected
):
    """A restored value must refer to today's currently active band."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    entity_id = "sensor.pun_prezzo_fascia_corrente"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "0.1"),
                {
                    "native_value": 0.1,
                    "data_date": saved_date,
                    "fascia": saved_band,
                    "friendly_name": f"Prezzo fascia corrente ({saved_band})",
                },
            )
        ],
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_download_failure_preserves_cache_without_clearing_error_on_clock_tick(
    hass, config_entry, freezer, aioclient_mock, price_archive
):
    """A local clock tick is not evidence of a successful network refresh."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    day = date(2026, 11, 12)
    aioclient_mock.get(GME_URL, content=price_archive([day]))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.update_pun()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.pun_mono_orario")
    assert float(state.state) == pytest.approx(0.1)

    aioclient_mock.clear_requests()
    aioclient_mock.get(GME_URL, status=503)
    await coordinator.update_pun()
    assert not coordinator.last_update_success
    freezer.move_to("2026-11-12T12:15:00+00:00")
    await coordinator.update_prezzo_zonale_15min()
    assert not coordinator.last_update_success
    state = hass.states.get("sensor.pun_mono_orario")
    assert float(state.state) == pytest.approx(0.1)
    assert state.attributes["dati_non_aggiornati"] is True
    assert state.attributes["dati_del"] == day.isoformat()

    aioclient_mock.clear_requests()
    aioclient_mock.get(GME_URL, content=price_archive([day], "200,0"))
    await coordinator.update_pun()
    assert coordinator.last_update_success
    state = hass.states.get("sensor.pun_mono_orario")
    assert float(state.state) == pytest.approx(0.2)
    assert state.attributes["dati_non_aggiornati"] is False
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_monthly_average_expires_at_italian_midnight(
    hass, config_entry, freezer, aioclient_mock, price_archive
):
    """Yesterday's monthly average must not appear to include today's prices."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    aioclient_mock.get(GME_URL, content=price_archive([date(2026, 11, 12)]))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.update_pun()
    freezer.move_to("2026-11-12T23:00:00+00:00")
    await coordinator.update_prezzo_zonale_15min()
    assert hass.states.get("sensor.pun_mono_orario").state == "unavailable"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize("saved_date", [None, "2026-11-11", "2026-11-12"])
async def test_restore_monthly_average_requires_today(
    hass, config_entry, freezer, saved_date
):
    """Legacy undated and previous-day monthly averages are not current data."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    entity_id = "sensor.pun_mono_orario"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "0.1"),
                {
                    "native_value": 0.1,
                    "data_date": saved_date,
                },
            )
        ],
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    expected = "0.1" if saved_date == "2026-11-12" else "unavailable"
    assert hass.states.get(entity_id).state == expected
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_manual_entity_refresh_updates_state(
    hass, config_entry, freezer, aioclient_mock, price_archive
):
    """The HA update_entity action must retain the coordinator's price event."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    assert await async_setup_component(hass, "homeassistant", {})
    aioclient_mock.get(GME_URL, content=price_archive([date(2026, 11, 12)], "300,0"))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "sensor.pun_mono_orario"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.pun_mono_orario").state) == pytest.approx(0.3)
    assert await hass.config_entries.async_unload(config_entry.entry_id)
