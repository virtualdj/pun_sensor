"""Reject ambiguous or malformed market intervals before replacing good data."""

from copy import deepcopy
from datetime import date
from io import BytesIO
from zipfile import ZipFile

import defusedxml.ElementTree as ET
import pytest

from custom_components.pun_sensor.coordinator import _parse_download
from custom_components.pun_sensor.interfaces import Fascia, PunData


def modified_archive(payload, modify):
    """Modify synthetic XML records while retaining the rest of the archive."""
    output = BytesIO()
    with ZipFile(BytesIO(payload)) as source, ZipFile(output, "w") as target:
        for name in source.namelist():
            root = ET.fromstring(source.read(name))
            extra = modify(name, root)
            target.writestr(name, ET.tostring(root))
            if extra:
                target.writestr(f"copy-{name}", ET.tostring(root))
    return output.getvalue()


@pytest.mark.parametrize("quarterly", [False, True])
@pytest.mark.parametrize("extra_file", [False, True])
def test_duplicate_intervals_are_rejected(price_archive, quarterly, extra_file):
    """Duplicate files and duplicate records must not bias monthly averages."""
    day = date(2026, 11, 12)
    valid = price_archive([day])
    previous = _parse_download(valid, PunData(), day)
    old_monthly = previous.pun[Fascia.MONO].copy()

    def duplicate(name, root):
        if ("Prezzi15" in name) != quarterly:
            return False
        if not extra_file:
            root.append(deepcopy(root[0]))
        return extra_file

    with pytest.raises(ValueError, match="duplicat"):
        _parse_download(modified_archive(valid, duplicate), previous, day)
    assert previous.pun[Fascia.MONO] == old_monthly


@pytest.mark.parametrize("quarterly", [False, True])
@pytest.mark.parametrize(
    "day", [date(2026, 3, 29), date(2026, 11, 12), date(2026, 10, 25)]
)
def test_out_of_day_periods_are_rejected(price_archive, quarterly, day):
    """Do not spill a nominal extra interval into tomorrow, including DST."""
    valid = price_archive([day])
    previous = _parse_download(valid, PunData(), day)

    def append_extra(name, root):
        if ("Prezzi15" in name) == quarterly:
            record = deepcopy(root[-1])
            tag = "Periodo" if quarterly else "Ora"
            record.find(tag).text = str(len(root) + 1)
            root.append(record)
        return False

    with pytest.raises(ValueError, match="non valido"):
        _parse_download(modified_archive(valid, append_extra), previous, day)


@pytest.mark.parametrize("quarterly", [False, True])
def test_record_dates_must_match_file_date(price_archive, quarterly):
    """A mixed-date XML must not silently relabel another day's price."""
    day = date(2026, 11, 12)
    valid = price_archive([day])

    def change_date(name, root):
        if ("Prezzi15" in name) == quarterly:
            root[-1].find("Data").text = "20261113"
        return False

    with pytest.raises(ValueError, match="Data incoerente"):
        _parse_download(modified_archive(valid, change_date), PunData(), day)
