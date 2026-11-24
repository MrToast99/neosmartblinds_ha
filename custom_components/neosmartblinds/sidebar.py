"""The optional sidebar page: the Neo Smart Blinds card as a page of its own.

New accounts have it on (the option is stored when the entry is created); an entry from an
earlier version has no such option and keeps it off. While at least one entry has it on,
one item is registered in Home Assistant's sidebar.

The item follows the config entries, not whether they are loaded. It stays through a
reload or a cloud outage, because the frontend sends anyone looking at a panel that
disappears back to their default dashboard (a wall tablet left on this page would not come
back by itself). For the same reason, changing the option takes effect on an entry that is
not loaded too.

The page is the <neosmartblinds-panel> element defined in the card's own file, loaded from
the same URL as the Lovelace card (see card.py). It asks the integration for its data
itself, so the panel needs no configuration.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
    ConfigEntryState,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .card import async_serve_card
from .const import CONF_SHOW_SIDEBAR, DOMAIN

# The page's address (/neosmartblinds). Dashboards must have a hyphen in theirs, so a
# user-made dashboard cannot already be using this one.
SIDEBAR_URL_PATH = DOMAIN
SIDEBAR_ELEMENT = "neosmartblinds-panel"
SIDEBAR_ICON = "mdi:blinds-horizontal"
SIDEBAR_TITLE = "Neo Blinds"

_LOGGER = logging.getLogger(__name__)

# State lives apart from hass.data[DOMAIN], which holds one item per config entry.
_DATA_KEY = f"{DOMAIN}_sidebar"

# An entry in one of these states brings the item up to date itself: setup and unload end
# with an update.
_UPDATES_ITSELF = (
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.UNLOAD_IN_PROGRESS,
)


def _safe_area_arguments() -> dict[str, bool]:
    """Tell newer frontends that the page keeps clear of the phone's notch itself."""
    parameters = inspect.signature(panel_custom.async_register_panel).parameters
    return {"handle_safe_area": True} if "handle_safe_area" in parameters else {}


def sidebar_enabled(entry: ConfigEntry) -> bool:
    """Whether this entry asks for the sidebar page (off unless the option was stored)."""
    return bool(entry.options.get(CONF_SHOW_SIDEBAR, False))


def _wanting_entries(hass: HomeAssistant, removed_entry_id: str | None) -> list[ConfigEntry]:
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != removed_entry_id and not entry.disabled_by and sidebar_enabled(entry)
    ]


@callback
def async_follow_entries(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Update the item when an entry that is not loaded changes.

    An entry whose setup is being retried, or that waits to be signed in again, has nothing
    running that would notice its option change.
    """

    @callback
    def _changed(change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if (
            change is ConfigEntryChange.UPDATED
            and entry.domain == DOMAIN
            and entry.state not in _UPDATES_ITSELF
            and not hass.is_stopping
        ):
            # Not eagerly: this runs inside Home Assistant's own bookkeeping of the entry.
            hass.async_create_task(
                async_update_sidebar_panel(hass), "neosmartblinds sidebar update", eager_start=False
            )

    return async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _changed)


async def async_update_sidebar_panel(
    hass: HomeAssistant, *, removed_entry_id: str | None = None
) -> None:
    """Add, refresh or remove the sidebar item so it matches the config entries.

    removed_entry_id names an entry that is being deleted: newer cores take it off their
    list first, older ones still list it then. Never raises: a problem here must not stop
    a config entry from loading.
    """
    data = hass.data.setdefault(_DATA_KEY, {"lock": asyncio.Lock()})
    async with data["lock"]:
        try:
            await _async_update(hass, data, removed_entry_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to update the Neo Smart Blinds sidebar page")


async def _async_update(
    hass: HomeAssistant, data: dict[str, Any], removed_entry_id: str | None
) -> None:
    registered = data.get("module_url")

    if not _wanting_entries(hass, removed_entry_id):
        if registered is not None:
            frontend.async_remove_panel(hass, SIDEBAR_URL_PATH)
            data.pop("module_url", None)
            _LOGGER.debug("Removed the Neo Smart Blinds sidebar page")
        return

    module_url = await async_serve_card(hass)
    if module_url is None or module_url == registered:
        return

    # Replace in one go, so a browser asking in between never sees the item missing.
    if registered is not None:
        frontend.async_remove_panel(hass, SIDEBAR_URL_PATH)
        data.pop("module_url", None)
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=SIDEBAR_URL_PATH,
            webcomponent_name=SIDEBAR_ELEMENT,
            sidebar_title=SIDEBAR_TITLE,
            sidebar_icon=SIDEBAR_ICON,
            module_url=module_url,
            embed_iframe=False,
            require_admin=False,
            **_safe_area_arguments(),
        )
    except ValueError:
        _LOGGER.warning(
            "Could not add the Neo Smart Blinds sidebar page: another panel already uses /%s",
            SIDEBAR_URL_PATH,
        )
        return
    data["module_url"] = module_url
    _LOGGER.debug("Neo Smart Blinds sidebar page registered")
