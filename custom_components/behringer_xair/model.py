"""Mixer addresses and value conversions, independent of Home Assistant."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Strip:
    """An audio strip with its actual X Air OSC paths."""

    key: str
    label: str
    path: str
    dca: bool = False

    @property
    def fader(self) -> str:
        return f"{self.path}/fader" if self.dca else f"{self.path}/mix/fader"

    @property
    def on(self) -> str:
        return f"{self.path}/on" if self.dca else f"{self.path}/mix/on"


STRIPS = (
    *(Strip(f"ch_{i:02}", f"Channel {i:02}", f"/ch/{i:02}") for i in range(1, 17)),
    Strip("aux", "Aux 17/18", "/rtn/aux"),
    Strip("main", "Main LR", "/lr"),
    *(Strip(f"bus_{i}", f"Bus {i}", f"/bus/{i}") for i in range(1, 7)),
    *(Strip(f"fx_{i}", f"FX return {i}", f"/rtn/{i}") for i in range(1, 5)),
    *(Strip(f"dca_{i}", f"DCA {i}", f"/dca/{i}", True) for i in range(1, 5)),
)


def fader_to_db(value: float) -> float:
    """Convert the segmented X Air fader curve; zero is represented as -90 dB."""
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Fader value must be between 0 and 1")
    if value >= 0.5:
        return value * 40 - 30
    if value >= 0.25:
        return value * 80 - 50
    if value >= 0.0625:
        return value * 160 - 70
    return value * 480 - 90


def db_to_fader(value: float) -> float:
    """Convert dB to the mixer's normalized fader position."""
    if not math.isfinite(value) or not -90 <= value <= 10:
        raise ValueError("Volume must be between -90 and +10 dB")
    if value >= -10:
        return (value + 30) / 40
    if value >= -30:
        return (value + 50) / 80
    if value >= -60:
        return (value + 70) / 160
    return (value + 90) / 480


def send_path(channel: int, bus: int) -> str:
    """Channel-to-bus sends use two-digit bus indexes, unlike bus masters."""
    if not 1 <= channel <= 16 or not 1 <= bus <= 6:
        raise ValueError("Invalid channel or bus")
    return f"/ch/{channel:02}/mix/{bus:02}/level"


def parse_snapshots(text: str) -> dict[int, str]:
    """Parse one slot or slot=name per line without silently dropping errors."""
    result: dict[int, str] = {}
    for line in text.splitlines():
        if not (line := line.strip()):
            continue
        slot_text, _, label = line.partition("=")
        slot = int(slot_text.strip())
        if not 1 <= slot <= 64 or slot in result:
            raise ValueError("Use unique snapshot slots from 1 to 64")
        if len(label.strip()) > 80:
            raise ValueError("Snapshot label is too long")
        result[slot] = label.strip() or f"Snapshot {slot:02}"
    return result
