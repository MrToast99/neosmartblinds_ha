"""Diagnostics for Neo Smart Blinds (Cloud).

Deliberately a summary rather than the raw cloud payload: that payload holds tokens and
controller strings. What is kept is what helps with a bug report, such as how many rooms,
blinds and schedules there are and which motor types the blinds report.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import (
    parse_blinds_from_data,
    parse_rooms_from_data,
    parse_schedules_from_data,
)
from .models import NeoSmartConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeoSmartConfigEntry
) -> dict[str, Any]:
    """Return a summary of the account, with the login and every name left out."""
    loaded = entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data.data if loaded else {}

    blinds = parse_blinds_from_data(data)
    rooms = parse_rooms_from_data(data)
    schedules = parse_schedules_from_data(data)

    return {
        "entry": {
            "title": "**REDACTED**",
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "state": str(entry.state),
        },
        "login_rejected": entry.runtime_data.api.auth_failed if loaded else None,
        "counts": {
            "rooms": len(rooms),
            "blinds": len(blinds),
            "schedules": len(schedules),
        },
        "rooms": [
            {
                "blinds": len(room["blind_codes"]),
                "motor_codes": sorted(set(room["motor_codes"].values())),
            }
            for room in rooms
        ],
        "blinds": [
            {
                "motor_code": blind["motor_code"],
                "has_percent": blind["has_percent"],
                "is_tdbu": blind["is_tdbu"],
            }
            for blind in blinds
        ],
        "schedules": [
            {"command": schedule.get("command"), "enabled": schedule.get("enabled")}
            for schedule in schedules
        ],
    }
