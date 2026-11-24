"""Builds what the Neo Smart Blinds card needs: each room with its entities.

Kept free of Home Assistant imports so it can be unit tested on its own. The caller passes the
parsed account data and a function that turns a (domain, unique id) pair into an entity id.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

EntityLookup = Callable[[str, str], "str | None"]


def build_card_info(accounts: Iterable[dict[str, Any]], lookup: EntityLookup) -> dict[str, Any]:
    """Return {"rooms": [...]} for every loaded account.

    Each item of ``accounts`` is {"entry_id", "rooms", "blinds", "schedules"}, the three lists
    coming from the parse_* functions in api.py.
    """
    rooms_out: list[dict[str, Any]] = []

    for account in accounts:
        entry_id = account["entry_id"]
        blinds_by_room: dict[str, list[dict]] = {}
        for blind in account.get("blinds", []):
            blinds_by_room.setdefault(blind.get("room_id"), []).append(blind)
        schedules_by_room: dict[str, list[dict]] = {}
        for schedule in account.get("schedules", []):
            schedules_by_room.setdefault(schedule.get("room"), []).append(schedule)

        for room in account.get("rooms", []):
            room_id = room.get("room_id")
            unique_id = room["unique_id"]

            blinds = []
            for blind in blinds_by_room.get(room_id, []):
                entity = lookup("cover", blind["unique_id"])
                if not entity:
                    continue
                blinds.append(
                    {
                        "name": blind.get("name") or blind["blind_code"],
                        "entity": entity,
                        "favorites": [
                            lookup("button", f"{blind['unique_id']}_fav_{n}") for n in (1, 2)
                        ],
                        "has_percent": bool(blind.get("has_percent")),
                    }
                )

            schedules = []
            for schedule in schedules_by_room.get(room_id, []):
                entity = lookup("switch", schedule["id"])
                if not entity:
                    continue
                schedules.append(
                    {
                        "entity": entity,
                        "name": schedule.get("name") or schedule["id"],
                        "time": schedule.get("time"),
                    }
                )
            schedules.sort(key=lambda s: (s["time"] or "", s["name"]))

            rooms_out.append(
                {
                    "id": f"{entry_id}:{room_id}",
                    "name": room.get("room_name") or room.get("name") or "Room",
                    "entity": lookup("cover", unique_id),
                    "favorites": [lookup("button", f"{unique_id}_fav_{n}") for n in (1, 2)],
                    "blinds": blinds,
                    "schedules": schedules,
                }
            )

    rooms_out.sort(key=lambda r: r["name"].casefold())
    return {"rooms": rooms_out}
