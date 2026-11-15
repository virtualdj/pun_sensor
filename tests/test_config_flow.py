"""Keep zone labels explicit without changing persisted market codes."""

import json
from pathlib import Path
import re
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.pun_sensor.config_flow import selector_config
from custom_components.pun_sensor.const import (
    CONF_ACTUAL_DATA_ONLY,
    CONF_SCAN_HOUR,
    CONF_ZONA,
    DOMAIN,
)
from custom_components.pun_sensor.interfaces import Zona
from homeassistant.config_entries import SOURCE_USER
from homeassistant.helpers.translation import async_get_translations


@pytest.mark.parametrize(
    "filename", ["strings.json", "translations/it.json", "translations/en.json"]
)
def test_zone_labels_preserve_codes_and_distinguish_foreign_zones(filename):
    """Every existing code gets a translated label, not a new stored value."""
    root = Path(__file__).parents[1] / "custom_components/pun_sensor"
    strings = json.loads((root / filename).read_text())
    labels = strings["selector"]["zona"]["options"]
    assert set(labels) == {zone.name.lower() for zone in Zona}
    assert all(re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", key) for key in labels)
    assert set(selector_config["options"]) == set(labels)
    assert selector_config["translation_key"] == "zona"
    italy = "Italy" if filename.endswith("en.json") else "Italia"
    for code in ("NORD", "CNOR", "CSUD", "SUD", "CALA", "SARD", "SICI", "NAT"):
        assert labels[code.lower()].startswith(f"{italy} (")
    for code in ("CORS", "COAC", "FRAN", "AUST", "MALT"):
        assert not labels[code.lower()].startswith(italy)
    assert len(set(labels.values())) == len(labels)


@pytest.mark.parametrize(
    ("language", "expected"), [("it", "Italia (Nord)"), ("en", "Italy (North)")]
)
async def test_home_assistant_loads_zone_translations(hass, language, expected):
    """Exercise HA's actual translation loader, not only the JSON structure."""
    translations = await async_get_translations(
        hass, language, "selector", {"pun_sensor"}
    )
    assert translations["component.pun_sensor.selector.zona.options.nord"] == expected


async def test_user_flow_persists_original_uppercase_zone(hass):
    """Lowercase selector IDs must not migrate the stored GME code."""
    with patch(
        "custom_components.pun_sensor.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_ZONA: "nord", CONF_SCAN_HOUR: 15, CONF_ACTUAL_DATA_ONLY: False},
        )
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["data"][CONF_ZONA] == "NORD"


async def test_options_flow_preserves_existing_zone_and_normalizes_new_selection(
    hass, config_entry
):
    """Existing uppercase settings select the matching lowercase UI option."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, CONF_SCAN_HOUR: 15, CONF_ACTUAL_DATA_ONLY: False},
    )
    form = await hass.config_entries.options.async_init(config_entry.entry_id)
    zone_field = next(
        key for key in form["data_schema"].schema if key.schema == CONF_ZONA
    )
    assert zone_field.default() == "nord"
    result = await hass.config_entries.options.async_configure(
        form["flow_id"],
        user_input={
            CONF_ZONA: "csud",
            CONF_SCAN_HOUR: 15,
            CONF_ACTUAL_DATA_ONLY: False,
        },
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_ZONA] == "CSUD"
