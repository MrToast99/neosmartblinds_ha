"""Tests for the websocket command the dashboard card uses."""
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.neosmartblinds.websocket_api import ws_card_info

from conftest import BLIND_1, BLIND_2, ROOM
from test_entities import entity_id


def ask(hass: HomeAssistant) -> dict:
    connection = MagicMock()
    ws_card_info(hass, connection, {"id": 7, "type": "neosmartblinds/card_info"})
    connection.send_result.assert_called_once()
    message_id, result = connection.send_result.call_args.args
    assert message_id == 7
    return result


async def test_card_info_lists_rooms_with_their_entities(
    hass: HomeAssistant, entry
) -> None:
    result = ask(hass)

    (room,) = result["rooms"]
    assert room["id"] == f"{entry.entry_id}:r1"
    assert room["name"] == "Dining"
    assert room["entity"] == entity_id(hass, "cover", ROOM)
    assert room["favorites"] == [
        entity_id(hass, "button", f"{ROOM}_fav_1"),
        entity_id(hass, "button", f"{ROOM}_fav_2"),
    ]
    assert [b["entity"] for b in room["blinds"]] == [
        entity_id(hass, "cover", BLIND_1),
        entity_id(hass, "cover", BLIND_2),
    ]
    assert [b["has_percent"] for b in room["blinds"]] == [True, False]
    assert room["schedules"] == [
        {
            "entity": entity_id(hass, "switch", "s1"),
            "name": "Dining Open at 7:00",
            "time": "7:00",
        }
    ]


async def test_card_info_skips_accounts_that_are_not_loaded(
    hass: HomeAssistant, entry
) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert ask(hass) == {"rooms": []}
