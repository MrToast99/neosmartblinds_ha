"""Tests for the diagnostics download."""
import json

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.neosmartblinds.diagnostics import (
    async_get_config_entry_diagnostics,
)

from conftest import CONTROLLER_ID, PASSWORD, USER_UUID, USERNAME


async def test_diagnostics_summarise_the_account(hass: HomeAssistant, entry) -> None:
    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["counts"] == {"rooms": 1, "blinds": 2, "schedules": 1}
    assert result["login_rejected"] is False
    assert result["rooms"] == [{"blinds": 2, "motor_codes": ["m1", "m2"]}]
    assert result["blinds"] == [
        {"motor_code": "m1", "has_percent": True, "is_tdbu": False},
        {"motor_code": "m2", "has_percent": False, "is_tdbu": True},
    ]
    assert result["schedules"] == [{"command": "up", "enabled": True}]
    assert result["entry"]["options"] == {"show_sidebar": False}


async def test_diagnostics_leave_out_everything_private(
    hass: HomeAssistant, entry
) -> None:
    text = json.dumps(await async_get_config_entry_diagnostics(hass, entry))

    for private in (USERNAME, PASSWORD, USER_UUID, CONTROLLER_ID, "Dining", "Slider", "abc"):
        assert private not in text, private


async def test_diagnostics_say_when_the_login_was_rejected(
    hass: HomeAssistant, entry, api
) -> None:
    api.reject_login()

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["login_rejected"] is True


async def test_diagnostics_work_for_an_account_that_is_not_loaded(
    hass: HomeAssistant, entry
) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["counts"] == {"rooms": 0, "blinds": 0, "schedules": 0}
    assert result["login_rejected"] is None
    assert PASSWORD not in json.dumps(result)
