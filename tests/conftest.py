"""Synthetic price archives and an isolated Home Assistant test environment."""

from collections.abc import Callable
from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pun_sensor.const import CONF_SCAN_MINUTE, CONF_ZONA, DOMAIN
from custom_components.pun_sensor.utils import get_total_hours


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow the real custom integration in the temporary HA instance."""


@pytest.fixture
def config_entry(hass) -> MockConfigEntry:
    """Register a synthetic config entry without device or account credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ZONA: "NORD", CONF_SCAN_MINUTE: 15}, version=2
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def price_archive() -> Callable[..., bytes]:
    """Build public-schema synthetic data without contacting GME."""

    def build(days: list[date], price: str = "100,0") -> bytes:
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for day in days:
                day_string = day.strftime("%Y%m%d")
                hours = get_total_hours(day)
                for quarterly in (False, True):
                    tag = "Prezzi15" if quarterly else "Prezzi"
                    period_tag = "Periodo" if quarterly else "Ora"
                    records = []
                    for period in range(1, hours * (4 if quarterly else 1) + 1):
                        granularity = (
                            "<Granularity>PT15</Granularity>" if quarterly else ""
                        )
                        records.append(
                            f"<{tag}><Data>{day_string}</Data><Mercato>MGP</Mercato>"
                            f"{granularity}<{period_tag}>{period}</{period_tag}>"
                            f"<PUN>{price}</PUN><NORD>{price}</NORD></{tag}>"
                        )
                    archive.writestr(
                        f"{day_string}MGP{tag}.xml",
                        "<NewDataSet>" + "".join(records) + "</NewDataSet>",
                    )
        return output.getvalue()

    return build
