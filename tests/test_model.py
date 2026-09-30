import math

import pytest

from custom_components.behringer_xair.model import (
    STRIPS,
    db_to_fader,
    fader_to_db,
    parse_snapshots,
    send_path,
)


@pytest.mark.parametrize(
    ("fader", "db"), [(0, -90), (0.0625, -60), (0.25, -30), (0.5, -10), (0.75, 0), (1, 10)]
)
def test_fader_landmarks(fader, db):
    assert fader_to_db(fader) == db
    assert db_to_fader(db) == fader


def test_complete_curve_is_monotonic_and_invertible():
    previous = -91
    for i in range(1025):
        fader = i / 1024
        db = fader_to_db(fader)
        assert db > previous
        assert db_to_fader(db) == pytest.approx(fader)
        previous = db


@pytest.mark.parametrize("value", [math.nan, math.inf, -1, 1.1])
def test_invalid_fader(value):
    with pytest.raises(ValueError):
        fader_to_db(value)


@pytest.mark.parametrize("value", [math.nan, math.inf, -91, 11])
def test_invalid_db(value):
    with pytest.raises(ValueError):
        db_to_fader(value)


def test_addresses_are_xair_not_x32():
    strips = {s.key: s for s in STRIPS}
    assert len(strips) == 32
    assert strips["main"].fader == "/lr/mix/fader"
    assert strips["bus_1"].on == "/bus/1/mix/on"
    assert strips["dca_1"].fader == "/dca/1/fader"
    assert strips["aux"].fader == "/rtn/aux/mix/fader"
    assert send_path(1, 1) == "/ch/01/mix/01/level"


def test_snapshot_names_and_empty():
    assert parse_snapshots("1=Spraak\n 64 = Muziek \n\n2") == {
        1: "Spraak",
        64: "Muziek",
        2: "Snapshot 02",
    }
    assert parse_snapshots("") == {}


@pytest.mark.parametrize("text", ["0", "65", "1.5", "1\n1=Duplicate", "abc", "1=" + "x" * 81])
def test_invalid_snapshots(text):
    with pytest.raises(ValueError):
        parse_snapshots(text)
