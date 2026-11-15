"""Exercise setup, unload and reload through the real HA config-entry manager."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.pun_sensor.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util


async def test_unload_cancels_all_timers(hass, config_entry, freezer):
    """No clock or network callback may reschedule after an entry is unloaded."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    with patch(
        "custom_components.pun_sensor.coordinator.PUNDataUpdateCoordinator._async_update_data",
        new_callable=AsyncMock,
    ) as download:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        old = hass.data[DOMAIN][config_entry.entry_id]
        before = (old.orario_prezzo, old.orario_prezzo_15min)
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED
        freezer.tick(timedelta(days=2))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        download.assert_not_awaited()
        assert (old.orario_prezzo, old.orario_prezzo_15min) == before


async def test_reload_does_not_duplicate_downloads(hass, config_entry, freezer):
    """Only the new coordinator downloads after reload."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    with patch(
        "custom_components.pun_sensor.coordinator.PUNDataUpdateCoordinator._async_update_data",
        new_callable=AsyncMock,
    ) as download:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert download.await_count == 1
        assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_unload_cancels_in_progress_download(hass, config_entry):
    """A pending download must not publish or reschedule after unload."""
    started = asyncio.Event()

    async def wait_for_response():
        started.set()
        await asyncio.Event().wait()

    with patch(
        "custom_components.pun_sensor.coordinator.PUNDataUpdateCoordinator._async_update_data",
        side_effect=wait_for_response,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        old = hass.data[DOMAIN][config_entry.entry_id]
        task = asyncio.create_task(old.update_pun())
        await started.wait()
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert old.schedule_token is None
        assert not old._clock_tokens
