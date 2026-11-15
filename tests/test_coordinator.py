"""Validate downloaded data without accessing the real GME endpoint."""

from contextlib import nullcontext
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from custom_components.pun_sensor.const import CONF_ACTUAL_DATA_ONLY, DOMAIN

from .test_sensor import GME_URL


@pytest.mark.parametrize(
    "invalid",
    [
        "html",
        "empty_zip",
        "yesterday",
        "missing_hour",
        "size_limit",
        "expanded_limit",
        "file_limit",
        "not_finite",
        "timeout",
    ],
)
async def test_invalid_download_preserves_last_good_data(
    *, hass, config_entry, freezer, aioclient_mock, price_archive, invalid
):
    """HTTP 200 alone must not replace current prices with invalid data."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    day = date(2026, 11, 12)
    valid = price_archive([day])
    aioclient_mock.get(GME_URL, content=valid)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.update_pun()
    previous = coordinator.pun_data
    last_success = coordinator.last_successful_update
    bad = valid
    limits = {}
    if invalid == "html":
        bad = b"<html>upstream temporarily unavailable</html>"
    elif invalid == "empty_zip":
        output = BytesIO()
        with ZipFile(output, "w"):
            pass
        bad = output.getvalue()
    elif invalid == "yesterday":
        bad = price_archive([day - timedelta(days=1)])
    elif invalid == "missing_hour":
        output = BytesIO()
        with ZipFile(BytesIO(valid)) as source, ZipFile(output, "w") as target:
            for name in source.namelist():
                xml = source.read(name)
                if "Prezzi15" not in name:
                    xml = xml.replace(b"<PUN>100,0</PUN>", b"", 1)
                target.writestr(name, xml)
        bad = output.getvalue()
    elif invalid == "size_limit":
        limits["MAX_DOWNLOAD_BYTES"] = 1
    elif invalid == "expanded_limit":
        limits["MAX_UNCOMPRESSED_BYTES"] = 1
    elif invalid == "file_limit":
        limits["MAX_ARCHIVE_FILES"] = 1
    elif invalid == "not_finite":
        bad = price_archive([day], "NaN")
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        GME_URL, content=bad, exc=TimeoutError if invalid == "timeout" else None
    )
    with (
        patch.multiple("custom_components.pun_sensor.coordinator", **limits)
        if limits
        else nullcontext()
    ):
        await coordinator.update_pun()
    assert not coordinator.last_update_success
    assert coordinator.pun_data is previous
    assert coordinator.last_successful_update == last_success
    assert float(hass.states.get("sensor.pun_mono_orario").state) == pytest.approx(0.1)
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_query_uses_italian_date_at_month_boundary(
    hass, config_entry, freezer, aioclient_mock, price_archive
):
    """Market dates must not depend on the HA instance's configured timezone."""
    freezer.move_to("2026-11-30T23:30:00+00:00")
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_ACTUAL_DATA_ONLY: True}
    )
    aioclient_mock.get(GME_URL, content=price_archive([date(2026, 12, 1)]))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.data[DOMAIN][config_entry.entry_id].update_pun()
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["DataInizio"] == "20261201"
    assert url.query["DataFine"] == "20261202"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
