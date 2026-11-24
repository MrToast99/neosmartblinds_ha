"""Shared fixtures for the tests that need Home Assistant."""
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neosmartblinds.const import CONF_SHOW_SIDEBAR, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

# What the integration lists under "dependencies" in manifest.json. Marking them as
# already set up keeps the tests from loading the whole frontend.
DEPENDENCIES = {"frontend", "http", "lovelace", "panel_custom", "websocket_api"}

USERNAME = "user@example.com"
PASSWORD = "old-password"
USER_UUID = "11111111-2222-3333-4444-555555555555"
CONTROLLER_ID = "ctrl-1"

# What the Neo cloud sends, cut down to what the integration reads: one room with two
# blinds (different motor types, only one reports percent) and one schedule.
SAMPLE_DATA = {
    "rooms": {
        "r1": {
            "name": "Dining",
            "controller": CONTROLLER_ID,
            "token": "abc",
            "blinds": {
                "1": {"name": "Slider", "hasPercent": True, "motorCode": "m1"},
                "2": {"name": "Left", "hasPercent": False, "motorCode": "m2", "tdbu": True},
            },
        }
    },
    "schedules": {
        "s1": {"room": "r1", "time": "7:00", "command": "up", "enabled": True},
    },
}

# unique ids the integration derives from SAMPLE_DATA
BLIND_1 = f"{CONTROLLER_ID}_abc-01"
BLIND_2 = f"{CONTROLLER_ID}_abc-02"
ROOM = f"room_r1_{CONTROLLER_ID}"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/ in this repository."""
    yield


@pytest.fixture(autouse=True)
def dependencies_ready(hass):
    """Pretend the integration's dependencies are set up."""
    hass.config.components.update(DEPENDENCIES)


class FakeAPI:
    """Stands in for NeoSmartCloudAPI: no network, and tests can drive its auth state."""

    def __init__(self) -> None:
        self.auth_failed = False
        self.auth_failed_callback: Callable[[], None] | None = None
        self._listeners: list[Callable[[], None]] = []
        self.async_login = AsyncMock()
        self.async_get_data = AsyncMock(return_value=SAMPLE_DATA)
        self.async_send_command = AsyncMock()
        self.async_set_schedule_state = AsyncMock()

    def async_add_auth_listener(self, listener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def reject_login(self) -> None:
        """What the real client does the first time the saved login is refused."""
        if self.auth_failed:
            return
        self.auth_failed = True
        for listener in list(self._listeners):
            listener()
        if self.auth_failed_callback:
            self.auth_failed_callback()


@pytest.fixture
def api_factory():
    """Replace the cloud client class; every client it hands out is in .created."""
    created: list[FakeAPI] = []

    def _make(*args, **kwargs) -> FakeAPI:
        created.append(FakeAPI())
        return created[-1]

    with patch(
        "custom_components.neosmartblinds.NeoSmartCloudAPI", side_effect=_make
    ) as factory:
        factory.created = created
        yield factory


@pytest.fixture
def no_frontend():
    """Skip the dashboard card, its resource and the sidebar page (they need the frontend).

    Yields the replacements, so a test can check what the integration asked them to do.
    """
    mocks = SimpleNamespace(
        serve_card=AsyncMock(),
        register_card=AsyncMock(),
        unregister_card=AsyncMock(),
        follow_entries=MagicMock(),
        update_sidebar=AsyncMock(),
    )
    with (
        patch("custom_components.neosmartblinds.async_serve_card", new=mocks.serve_card),
        patch("custom_components.neosmartblinds.async_register_card", new=mocks.register_card),
        patch("custom_components.neosmartblinds.async_unregister_card", new=mocks.unregister_card),
        patch("custom_components.neosmartblinds.async_follow_entries", new=mocks.follow_entries),
        patch(
            "custom_components.neosmartblinds.async_update_sidebar_panel",
            new=mocks.update_sidebar,
        ),
    ):
        yield mocks


def make_entry(**overrides) -> MockConfigEntry:
    values = {
        "domain": DOMAIN,
        "data": {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        "options": {CONF_SHOW_SIDEBAR: False},
        "unique_id": USER_UUID,
        "title": f"Neo Blinds ({USERNAME})",
    }
    values.update(overrides)
    return MockConfigEntry(**values)


@pytest.fixture
async def entry(
    hass: HomeAssistant, api_factory, no_frontend
) -> MockConfigEntry:
    """A loaded account built from SAMPLE_DATA."""
    config_entry = make_entry()
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def api(entry, api_factory) -> FakeAPI:
    """The cloud client of the loaded account."""
    return api_factory.created[-1]
