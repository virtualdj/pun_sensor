"""Changing market zone must not relabel the previous zone's prices."""

from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest

from custom_components.pun_sensor.const import CONF_ZONA, DOMAIN
from custom_components.pun_sensor.interfaces import Zona

from .test_sensor import GME_URL


@pytest.mark.parametrize("response", ["failure", "hourly_only", "complete"])
async def test_zone_change_discards_old_zonal_cache(
    *, hass, config_entry, freezer, aioclient_mock, price_archive, response
):
    """Reload through HA, preserving national prices but never old zonal data."""
    freezer.move_to("2026-11-12T12:00:00+00:00")
    day = date(2026, 11, 12)
    aioclient_mock.get(GME_URL, content=price_archive([day]))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    old = hass.data[DOMAIN][config_entry.entry_id]
    await old.update_pun()
    assert float(hass.states.get("sensor.pun_prezzo_zonale_15min").state) == 0.1

    hass.config_entries.async_update_entry(config_entry, options={CONF_ZONA: "SUD"})
    await hass.async_block_till_done()
    current = hass.data[DOMAIN][config_entry.entry_id]
    assert current is not old
    assert old._stopped
    assert current.pun_data.zona is Zona.SUD
    for entity in ("sensor.pun_prezzo_zonale", "sensor.pun_prezzo_zonale_15min"):
        assert hass.states.get(entity).state == "unavailable"
    assert float(hass.states.get("sensor.pun_orario").state) == 0.1

    aioclient_mock.clear_requests()
    output = BytesIO()
    with (
        ZipFile(BytesIO(price_archive([day], "200,0"))) as source,
        ZipFile(output, "w") as target,
    ):
        for name in source.namelist():
            if response == "hourly_only" and "Prezzi15" in name:
                continue
            xml = source.read(name).replace(b"NORD", b"SUD")
            target.writestr(name, xml)
    if response == "failure":
        aioclient_mock.get(GME_URL, status=503)
    else:
        aioclient_mock.get(GME_URL, content=output.getvalue())
    await current.update_pun()
    hourly = hass.states.get("sensor.pun_prezzo_zonale")
    quarterly = hass.states.get("sensor.pun_prezzo_zonale_15min")
    assert hourly.state == ("unavailable" if response == "failure" else "0.2")
    assert quarterly.state == ("0.2" if response == "complete" else "unavailable")
    if response == "complete":
        assert quarterly.attributes["friendly_name"].endswith("(Sud)")
    assert await hass.config_entries.async_unload(config_entry.entry_id)
