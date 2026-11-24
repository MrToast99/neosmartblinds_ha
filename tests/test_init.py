"""Tests for setting up, reloading and removing an account."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.neosmartblinds import ACCOUNT_DEVICE_MODEL
from custom_components.neosmartblinds.api import NeoSmartCloudAuthError
from custom_components.neosmartblinds.const import DOMAIN

from conftest import BLIND_1, CONTROLLER_ID, ROOM, USERNAME, make_entry


def device(hass: HomeAssistant, entry, identifier: str):
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, identifier), entry.entry_id
    )


def reauth_flows(hass: HomeAssistant) -> list:
    return [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == "reauth"
    ]


async def test_setup_builds_the_device_tree(hass: HomeAssistant, entry) -> None:
    assert entry.state is ConfigEntryState.LOADED

    account = device(hass, entry, USERNAME)
    controller = device(hass, entry, CONTROLLER_ID)
    blind = device(hass, entry, BLIND_1)
    room = device(hass, entry, ROOM)

    assert account.model == ACCOUNT_DEVICE_MODEL
    assert account.name == f"Neo Blinds ({USERNAME})"
    assert controller.name == "Neo Controller (Dining)"
    assert controller.via_device_id == account.id
    assert blind.name == "Slider"
    assert blind.via_device_id == room.id  # Controller > Room > Blind
    assert room.name == "Room: Dining"
    assert room.model == "Room"
    assert room.via_device_id == controller.id


async def test_unload_and_reload(hass: HomeAssistant, entry, api_factory) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(api_factory.created) == 2  # a fresh client signed in again


async def test_a_rejected_login_at_setup_starts_reauthentication(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)

    # The first client the integration builds refuses the login.
    original_side_effect = api_factory.side_effect

    def _failing_client(*args, **kwargs):
        client = original_side_effect(*args, **kwargs)
        client.async_login.side_effect = NeoSmartCloudAuthError("bad login")
        return client

    api_factory.side_effect = _failing_client

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(reauth_flows(hass)) == 1


async def test_an_unreachable_cloud_at_setup_is_retried(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    original_side_effect = api_factory.side_effect

    def _failing_client(*args, **kwargs):
        client = original_side_effect(*args, **kwargs)
        client.async_login.side_effect = ConnectionError("no route")
        return client

    api_factory.side_effect = _failing_client

    assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not reauth_flows(hass)  # not a password problem


async def test_a_login_rejected_while_running_starts_reauthentication(
    hass: HomeAssistant, entry, api
) -> None:
    assert not reauth_flows(hass)

    api.reject_login()
    api.reject_login()  # reported once, however often commands fail
    await hass.async_block_till_done()

    assert len(reauth_flows(hass)) == 1


async def test_changing_the_email_replaces_the_account_device(
    hass: HomeAssistant, entry
) -> None:
    old_account = device(hass, entry, USERNAME)
    controller = device(hass, entry, CONTROLLER_ID)
    assert controller.via_device_id == old_account.id

    hass.config_entries.async_update_entry(
        entry,
        data={CONF_USERNAME: "new@example.com", CONF_PASSWORD: entry.data[CONF_PASSWORD]},
    )
    await hass.async_block_till_done()  # the update reloads the entry

    assert entry.state is ConfigEntryState.LOADED
    assert device(hass, entry, USERNAME) is None
    new_account = device(hass, entry, "new@example.com")
    assert new_account is not None
    assert device(hass, entry, CONTROLLER_ID).via_device_id == new_account.id
    # Nothing else about the devices changed: blinds keep their devices and entities.
    assert device(hass, entry, BLIND_1) is not None


async def test_removing_the_account_cleans_up(hass: HomeAssistant, entry) -> None:
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert device(hass, entry, USERNAME) is None
