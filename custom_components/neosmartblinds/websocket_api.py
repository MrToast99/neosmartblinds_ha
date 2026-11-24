"""Websocket command the Neo Smart Blinds card uses to find its rooms and entities."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .api import parse_blinds_from_data, parse_rooms_from_data, parse_schedules_from_data
from .card_data import build_card_info
from .const import DOMAIN


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/card_info"})
@callback
def ws_card_info(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Rooms, blinds and schedules of every loaded account, with their entity ids."""
    registry = er.async_get(hass)
    accounts = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if not entry_data:
            continue  # not loaded
        data = entry_data["data"]
        accounts.append(
            {
                "entry_id": entry.entry_id,
                "rooms": parse_rooms_from_data(data),
                "blinds": parse_blinds_from_data(data),
                "schedules": parse_schedules_from_data(data),
            }
        )

    connection.send_result(
        msg["id"],
        build_card_info(
            accounts,
            lambda domain, unique_id: registry.async_get_entity_id(domain, DOMAIN, unique_id),
        ),
    )


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the card's websocket command (once per run)."""
    websocket_api.async_register_command(hass, ws_card_info)
