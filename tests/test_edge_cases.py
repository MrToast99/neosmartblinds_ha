"""Tests for the paths the main tests don't reach: empty accounts, early startup, cancellation."""
import asyncio

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant

from custom_components.neosmartblinds.entity import async_send_to_blinds

from conftest import SAMPLE_DATA, FakeAPI, make_entry


async def test_an_account_with_nothing_in_it_loads(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    original = api_factory.side_effect

    def empty_account(*args, **kwargs):
        client = original(*args, **kwargs)
        client.async_get_data.return_value = {"rooms": {}, "schedules": {}}
        return client

    api_factory.side_effect = empty_account
    entry = make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("cover")
    assert not hass.states.async_entity_ids("switch")


async def test_an_account_without_schedules_has_no_switches(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    original = api_factory.side_effect

    def no_schedules(*args, **kwargs):
        client = original(*args, **kwargs)
        client.async_get_data.return_value = {"rooms": SAMPLE_DATA["rooms"]}
        return client

    api_factory.side_effect = no_schedules
    entry = make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert hass.states.async_entity_ids("cover")
    assert not hass.states.async_entity_ids("switch")


async def test_the_card_waits_for_startup_when_loaded_early(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    hass.set_state(CoreState.starting)
    entry = make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    no_frontend.register_card.assert_not_awaited()  # Lovelace may not be ready yet

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    no_frontend.register_card.assert_awaited_once()


async def test_the_card_is_registered_straight_away_when_running(
    hass: HomeAssistant, entry, no_frontend
) -> None:
    no_frontend.register_card.assert_awaited_once()
    no_frontend.follow_entries.assert_called_once()
    no_frontend.update_sidebar.assert_awaited()


async def test_removing_the_last_account_removes_the_card(
    hass: HomeAssistant, entry, no_frontend
) -> None:
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    no_frontend.unregister_card.assert_awaited_once()


async def test_removing_one_of_two_accounts_keeps_the_card(
    hass: HomeAssistant, entry, api_factory, no_frontend
) -> None:
    second = make_entry(unique_id="second-account", data={**entry.data, "username": "b@example.com"})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(second.entry_id)
    await hass.async_block_till_done()

    no_frontend.unregister_card.assert_not_awaited()


async def test_cancelling_a_room_command_is_not_swallowed() -> None:
    api = FakeAPI()
    api.async_send_command.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await async_send_to_blinds(api, "ctrl", ["a-01"], {}, "up")
