"""Run protocol tests without HA, and full integration tests with the HA plugin."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if not HAS_HA:
    # Load the standalone protocol modules without executing the HA entrypoint.
    package = types.ModuleType("custom_components.behringer_xair")
    package.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "behringer_xair")]
    sys.modules[package.__name__] = package


@pytest.fixture(autouse=True)
def custom_integration(request):
    if HAS_HA:
        request.getfixturevalue("enable_custom_integrations")
        request.getfixturevalue("socket_enabled")


@pytest.fixture
async def mixer():
    from .fake_mixer import FakeMixer

    device = FakeMixer()
    await device.start()
    yield device
    device.close()
