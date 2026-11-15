"""Regression tests for the actual price parser, including DST and failed input."""

from datetime import date, datetime, timedelta
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import ZipFile

import pytest

from custom_components.pun_sensor.interfaces import Fascia, PunData, Zona
from custom_components.pun_sensor.utils import extract_xml


def parse(payload: bytes, data: PunData, day: date) -> PunData:
    """Parse an archive with the production code."""
    with ZipFile(BytesIO(payload)) as archive:
        return extract_xml(archive, data, day)


@pytest.mark.parametrize(
    ("day", "hours"),
    [(date(2026, 3, 29), 23), (date(2026, 11, 12), 24), (date(2026, 10, 25), 25)],
)
def test_dst_periods(price_archive, day, hours):
    """Preserve every distinct offset-qualified interval on DST days."""
    data = PunData()
    data.zona = Zona.NORD
    result = parse(price_archive([day]), data, day)
    assert len(result.pun_orari) == hours
    assert len(result.prezzi_zonali) == hours
    assert len(result.pun_15min) == hours * 4
    assert len(result.prezzi_zonali_15min) == hours * 4
    instants = [datetime.fromisoformat(key).timestamp() for key in result.pun_15min]
    assert len(set(instants)) == hours * 4


@pytest.mark.parametrize(
    ("raw", "expected"), [("0,0", 0), ("-10,0", -0.01), ("1.234,56", 1.23456)]
)
def test_price_conversion(price_archive, raw, expected):
    """Do not discard zero or negative prices; convert EUR/MWh to EUR/kWh."""
    day = date(2026, 11, 12)
    result = parse(price_archive([day], raw), PunData(), day)
    assert list(result.pun_orari.values()) == pytest.approx([expected] * 24)
    assert list(result.pun_15min.values()) == pytest.approx([expected] * 96)


def test_cache_replaced_without_mutating_previous_data(price_archive):
    """Remove obsolete days while retaining the previous snapshot unmodified."""
    day = date(2026, 11, 12)
    tomorrow = day + timedelta(days=1)
    initial = PunData()
    initial.zona = Zona.NORD
    previous = parse(price_archive([day, tomorrow]), initial, day)
    old_prices = previous.pun_orari.copy()
    result = parse(
        price_archive([day, tomorrow, tomorrow + timedelta(days=1)]), previous, tomorrow
    )
    assert previous.pun_orari == old_prices
    assert result.zona == Zona.NORD
    for prices in (
        result.pun_orari,
        result.prezzi_zonali,
        result.pun_15min,
        result.prezzi_zonali_15min,
    ):
        assert {datetime.fromisoformat(key).date() for key in prices} == {
            tomorrow,
            tomorrow + timedelta(days=1),
        }
    assert len(result.pun[Fascia.MONO]) == 48


def test_invalid_xml_does_not_destroy_previous_snapshot(price_archive):
    """An error after partial parsing must not change the last good data."""
    day = date(2026, 11, 12)
    previous = parse(price_archive([day]), PunData(), day)
    old_monthly = previous.pun[Fascia.MONO].copy()
    broken = BytesIO(price_archive([day], "200,0"))
    with ZipFile(broken, "a") as archive:
        archive.writestr("zzz-broken.xml", "<broken")
    with pytest.raises(ParseError):
        parse(broken.getvalue(), previous, day)
    assert previous.pun[Fascia.MONO] == old_monthly


def test_only_today_and_tomorrow_are_retained(price_archive):
    """Do not keep distant future days in interval-price caches."""
    day = date(2026, 11, 12)
    result = parse(
        price_archive([day + timedelta(days=n) for n in range(3)]), PunData(), day
    )
    assert len(result.pun_orari) == 48
    assert len(result.pun_15min) == 192
