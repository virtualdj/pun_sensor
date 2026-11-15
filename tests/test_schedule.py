"""Exercise daily downloads and local-day boundaries without real network I/O."""

from datetime import date, timedelta

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.pun_sensor.const import (
    CONF_ACTUAL_DATA_ONLY,
    CONF_SCAN_HOUR,
    DOMAIN,
)
from homeassistant.util import dt as dt_util

from .test_sensor import GME_URL


async def test_automatic_daily_download(
    hass, config_entry, freezer, aioclient_mock, price_archive
):
    """HA timers must fetch once at boot and again at the configured15:15."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_SCAN_HOUR: 15}
    )
    days = [date(2026, 11, 12), date(2026, 11, 13)]
    aioclient_mock.get(GME_URL, content=price_archive(days))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 1
    assert float(hass.states.get("sensor.pun_prezzo_zonale").state) == 0.1

    aioclient_mock.clear_requests()
    aioclient_mock.get(GME_URL, content=price_archive(days, "200,0"))
    freezer.move_to("2026-11-12T14:15:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 1
    assert float(hass.states.get("sensor.pun_prezzo_zonale").state) == 0.2
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize("day_string", ["2026-11-12", "2026-11-30"])
async def test_midnight_uses_cached_next_day_without_old_monthly_average(
    *, hass, config_entry, freezer, aioclient_mock, price_archive, day_string
):
    """Today becomes tomorrow correctly, including the November/December boundary."""
    freezer.move_to(f"{day_string}T15:00:00+00:00")
    day = date.fromisoformat(day_string)
    tomorrow = day + timedelta(days=1)
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, CONF_SCAN_HOUR: 15, CONF_ACTUAL_DATA_ONLY: True},
    )
    aioclient_mock.get(GME_URL, content=price_archive([day, tomorrow]))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.update_pun()
    calls_before_midnight = len(aioclient_mock.mock_calls)

    freezer.move_to(f"{day}T23:00:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert coordinator.orario_prezzo.date() == tomorrow
    for entity in ("sensor.pun_orario", "sensor.pun_prezzo_zonale_15min"):
        assert float(hass.states.get(entity).state) == 0.1
    assert hass.states.get("sensor.pun_mono_orario").state == "unavailable"
    assert len(aioclient_mock.mock_calls) == calls_before_midnight
    assert await hass.config_entries.async_unload(config_entry.entry_id)
