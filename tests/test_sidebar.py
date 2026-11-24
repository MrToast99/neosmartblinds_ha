"""Tests for the optional sidebar page."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntryChange,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.neosmartblinds import sidebar
from custom_components.neosmartblinds.const import CONF_SHOW_SIDEBAR
from custom_components.neosmartblinds.sidebar import (
    SIDEBAR_ELEMENT,
    SIDEBAR_URL_PATH,
    async_follow_entries,
    async_update_sidebar_panel,
    sidebar_enabled,
)

from conftest import make_entry

URL = "/neosmartblinds_static/neosmartblinds-card.js?v=1"


@pytest.fixture
def panels():
    """Replace everything that touches the frontend."""
    serve = AsyncMock(return_value=URL)
    register = AsyncMock()
    remove = MagicMock()
    with (
        patch.object(sidebar, "async_serve_card", serve),
        patch.object(sidebar.panel_custom, "async_register_panel", register),
        patch.object(sidebar.frontend, "async_remove_panel", remove),
    ):
        yield SimpleNamespace(serve=serve, register=register, remove=remove)


def add_entry(hass: HomeAssistant, **options):
    entry = make_entry(options=options)
    entry.add_to_hass(hass)
    return entry


def test_the_option_defaults_to_off_for_older_accounts() -> None:
    assert sidebar_enabled(make_entry(options={})) is False
    assert sidebar_enabled(make_entry(options={CONF_SHOW_SIDEBAR: False})) is False
    assert sidebar_enabled(make_entry(options={CONF_SHOW_SIDEBAR: True})) is True


async def test_the_page_is_added_when_an_account_wants_it(
    hass: HomeAssistant, panels
) -> None:
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})

    await async_update_sidebar_panel(hass)

    panels.register.assert_awaited_once()
    kwargs = panels.register.await_args.kwargs
    assert kwargs["frontend_url_path"] == SIDEBAR_URL_PATH
    assert kwargs["webcomponent_name"] == SIDEBAR_ELEMENT
    assert kwargs["module_url"] == URL
    panels.remove.assert_not_called()


async def test_asking_again_changes_nothing(hass: HomeAssistant, panels) -> None:
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})

    await async_update_sidebar_panel(hass)
    await async_update_sidebar_panel(hass)

    panels.register.assert_awaited_once()


async def test_a_new_card_version_replaces_the_page(hass: HomeAssistant, panels) -> None:
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})
    await async_update_sidebar_panel(hass)

    panels.serve.return_value = URL.replace("v=1", "v=2")
    await async_update_sidebar_panel(hass)

    panels.remove.assert_called_once_with(hass, SIDEBAR_URL_PATH)
    assert panels.register.await_count == 2


async def test_the_page_is_removed_when_nobody_wants_it(
    hass: HomeAssistant, panels
) -> None:
    entry = add_entry(hass, **{CONF_SHOW_SIDEBAR: True})
    await async_update_sidebar_panel(hass)

    hass.config_entries.async_update_entry(entry, options={CONF_SHOW_SIDEBAR: False})
    await async_update_sidebar_panel(hass)

    panels.remove.assert_called_once_with(hass, SIDEBAR_URL_PATH)


async def test_nothing_to_remove_when_it_was_never_added(
    hass: HomeAssistant, panels
) -> None:
    add_entry(hass, **{CONF_SHOW_SIDEBAR: False})

    await async_update_sidebar_panel(hass)

    panels.register.assert_not_awaited()
    panels.remove.assert_not_called()


async def test_a_disabled_account_does_not_keep_the_page(
    hass: HomeAssistant, panels
) -> None:
    make_entry(
        options={CONF_SHOW_SIDEBAR: True}, disabled_by=ConfigEntryDisabler.USER
    ).add_to_hass(hass)

    await async_update_sidebar_panel(hass)

    panels.register.assert_not_awaited()


async def test_a_deleted_account_is_left_out(hass: HomeAssistant, panels) -> None:
    entry = add_entry(hass, **{CONF_SHOW_SIDEBAR: True})
    await async_update_sidebar_panel(hass)

    await async_update_sidebar_panel(hass, removed_entry_id=entry.entry_id)

    panels.remove.assert_called_once()


async def test_without_the_card_file_there_is_no_page(hass: HomeAssistant, panels) -> None:
    panels.serve.return_value = None
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})

    await async_update_sidebar_panel(hass)

    panels.register.assert_not_awaited()


async def test_a_taken_address_is_reported_not_raised(
    hass: HomeAssistant, panels, caplog
) -> None:
    panels.register.side_effect = ValueError("already used")
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})

    await async_update_sidebar_panel(hass)

    assert "another panel already uses" in caplog.text


async def test_a_problem_with_the_page_never_stops_an_account_loading(
    hass: HomeAssistant, panels, caplog
) -> None:
    panels.serve.side_effect = RuntimeError("boom")
    add_entry(hass, **{CONF_SHOW_SIDEBAR: True})

    await async_update_sidebar_panel(hass)  # must not raise

    assert "Failed to update the Neo Smart Blinds sidebar page" in caplog.text


@pytest.mark.parametrize("has_argument", [True, False])
def test_newer_frontends_are_told_about_the_notch(has_argument: bool) -> None:
    def register(hass, handle_safe_area=False):
        ...

    def register_old(hass):
        ...

    function = register if has_argument else register_old
    with patch.object(sidebar.panel_custom, "async_register_panel", function):
        assert sidebar._safe_area_arguments() == ({"handle_safe_area": True} if has_argument else {})


# --- following entries that are not loaded --------------------------------------------


@pytest.fixture
def follow(hass: HomeAssistant):
    """(page update mock, subscribe): subscribe after the test has set its entries up,
    because Home Assistant itself sends the entry-changed signal while they are."""
    update = AsyncMock()
    unsubscribers = []
    with patch.object(sidebar, "async_update_sidebar_panel", update):

        def subscribe():
            unsubscribers.append(async_follow_entries(hass))

        yield SimpleNamespace(update=update, subscribe=subscribe)
        for unsubscribe in unsubscribers:
            unsubscribe()


async def change(hass: HomeAssistant, entry, kind=ConfigEntryChange.UPDATED) -> None:
    async_dispatcher_send(hass, SIGNAL_CONFIG_ENTRY_CHANGED, kind, entry)
    await hass.async_block_till_done()


async def test_an_option_change_on_a_retrying_account_updates_the_page(
    hass: HomeAssistant, follow
) -> None:
    entry = add_entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    await hass.async_block_till_done()
    follow.subscribe()

    await change(hass, entry)

    follow.update.assert_awaited_once_with(hass)


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.LOADED,
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.UNLOAD_IN_PROGRESS,
    ],
)
async def test_accounts_that_update_the_page_themselves_are_not_followed(
    hass: HomeAssistant, follow, state
) -> None:
    entry = add_entry(hass)
    entry.mock_state(hass, state)
    await hass.async_block_till_done()
    follow.subscribe()

    await change(hass, entry)

    follow.update.assert_not_awaited()


async def test_other_kinds_of_change_are_ignored(hass: HomeAssistant, follow) -> None:
    entry = add_entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    await hass.async_block_till_done()
    follow.subscribe()

    await change(hass, entry, ConfigEntryChange.ADDED)

    follow.update.assert_not_awaited()


async def test_other_integrations_are_ignored(hass: HomeAssistant, follow) -> None:
    entry = add_entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    await hass.async_block_till_done()
    follow.subscribe()
    other = SimpleNamespace(domain="something_else", state=entry.state)

    await change(hass, other)

    follow.update.assert_not_awaited()


async def test_nothing_is_updated_while_stopping(hass: HomeAssistant, follow) -> None:
    entry = add_entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY)
    await hass.async_block_till_done()
    follow.subscribe()

    with patch.object(type(hass), "is_stopping", True, create=True):
        await change(hass, entry)

    follow.update.assert_not_awaited()
