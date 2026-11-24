"""Tests for rooms as devices: one controller can serve several rooms."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.neosmartblinds.const import DOMAIN

from conftest import CONTROLLER_ID, ROOM, SAMPLE_DATA, make_entry
from test_entities import entity_id

GUEST_ROOM = f"room_r2_{CONTROLLER_ID}"

# Two rooms on the same controller, as in a home where one controller serves everything.
TWO_ROOMS = {
    "rooms": {
        **SAMPLE_DATA["rooms"],
        "r2": {
            "name": "Guest",
            "controller": CONTROLLER_ID,
            "token": "def",
            "blinds": {"1": {"name": "Guest Left", "hasPercent": True, "motorCode": "m1"}},
        },
    },
    "schedules": {},
}


def serve(api_factory, data) -> None:
    original = api_factory.side_effect

    def with_data(*args, **kwargs):
        client = original(*args, **kwargs)
        client.async_get_data.return_value = data
        return client

    api_factory.side_effect = with_data


async def test_rooms_on_one_controller_keep_their_own_names(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    serve(api_factory, TWO_ROOMS)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def state(domain: str, unique_id: str):
        return hass.states.get(entity_id(hass, domain, unique_id))

    assert state("cover", ROOM).name == "Room: Dining"
    assert state("cover", GUEST_ROOM).name == "Room: Guest"
    assert state("button", f"{ROOM}_fav_1").name == "Room: Dining Favorite 1"
    assert state("button", f"{GUEST_ROOM}_fav_1").name == "Room: Guest Favorite 1"
    # Names that differ also mean entity ids that differ, with no "_2" to tell them apart.
    assert entity_id(hass, "cover", ROOM) == "cover.room_dining"
    assert entity_id(hass, "cover", GUEST_ROOM) == "cover.room_guest"


async def test_each_room_is_a_device_under_its_controller(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    serve(api_factory, TWO_ROOMS)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    devices = dr.async_get(hass)

    controller = devices.async_get_device_by_identifier((DOMAIN, CONTROLLER_ID), entry.entry_id)
    dining = devices.async_get_device_by_identifier((DOMAIN, ROOM), entry.entry_id)
    guest = devices.async_get_device_by_identifier((DOMAIN, GUEST_ROOM), entry.entry_id)

    assert (dining.name, guest.name) == ("Room: Dining", "Room: Guest")
    assert dining.via_device_id == guest.via_device_id == controller.id
    # The room's entities are on the room's device, not on the shared controller.
    registry = er.async_get(hass)
    for room_device, unique_id in ((dining, ROOM), (guest, GUEST_ROOM)):
        for domain, uid in (
            ("cover", unique_id),
            ("button", f"{unique_id}_fav_1"),
            ("button", f"{unique_id}_fav_2"),
        ):
            entity = registry.async_get(entity_id(hass, domain, uid))
            assert entity.device_id == room_device.id, uid


async def test_room_entities_from_an_older_version_move_to_the_room_device(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    """Before, room entities sat on the controller's device. Loading moves them."""
    entry = make_entry()
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    controller = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, CONTROLLER_ID)}
    )
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "cover", DOMAIN, ROOM, config_entry=entry, device_id=controller.id
    )
    assert old.device_id == controller.id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    moved = registry.async_get(old.entity_id)
    room = devices.async_get_device_by_identifier((DOMAIN, ROOM), entry.entry_id)
    assert moved.entity_id == old.entity_id  # same entity, so history and dashboards stay
    assert moved.device_id == room.id
    assert hass.states.get(old.entity_id).name == "Room: Dining"


# --- schedules ----------------------------------------------------------------------

SCHEDULES = {
    "rooms": {
        **TWO_ROOMS["rooms"],
        # A room with no blinds: it gets no device, so its schedules fall back to the controller.
        "r3": {"name": "Empty", "controller": CONTROLLER_ID, "token": "ghi", "blinds": {}},
    },
    "schedules": {
        "s1": {"room": "r1", "time": "7:00", "command": "up", "enabled": True},
        "s2": {"room": "r2", "time": "20:00", "command": "dn", "enabled": False},
        "s3": {"room": "r3", "time": "8:00", "command": "up", "enabled": True},
        "s4": {"room": "gone", "time": "1:00", "command": "dn", "enabled": True},
    },
}


async def test_schedules_sit_on_their_room_s_device(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    serve(api_factory, SCHEDULES)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    devices = dr.async_get(hass)
    registry = er.async_get(hass)

    def where(schedule_id: str):
        entity = registry.async_get(entity_id(hass, "switch", schedule_id))
        return devices.async_get(entity.device_id) if entity.device_id else None

    dining = devices.async_get_device_by_identifier((DOMAIN, ROOM), entry.entry_id)
    guest = devices.async_get_device_by_identifier((DOMAIN, GUEST_ROOM), entry.entry_id)
    controller = devices.async_get_device_by_identifier((DOMAIN, CONTROLLER_ID), entry.entry_id)

    assert where("s1").id == dining.id
    assert where("s2").id == guest.id
    assert where("s3").id == controller.id  # its room has no device
    assert where("s4") is None  # its room is unknown

    def name(schedule_id: str) -> str:
        return hass.states.get(entity_id(hass, "switch", schedule_id)).name

    assert name("s1") == "Room: Dining Open at 7:00"
    assert name("s2") == "Room: Guest Close at 20:00"
    assert name("s3") == "Neo Controller (Dining) Empty Open at 8:00"
    assert name("s4") == "Unknown Room Close at 1:00"


async def test_schedules_from_an_older_version_move_to_the_room_device(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    controller = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, CONTROLLER_ID)}
    )
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "switch", DOMAIN, "s1", config_entry=entry, device_id=controller.id
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    moved = registry.async_get(old.entity_id)
    room = devices.async_get_device_by_identifier((DOMAIN, ROOM), entry.entry_id)
    assert moved.entity_id == old.entity_id
    assert moved.device_id == room.id


async def test_blinds_sit_under_their_own_room(
    hass: HomeAssistant, api_factory, no_frontend
) -> None:
    serve(api_factory, TWO_ROOMS)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    devices = dr.async_get(hass)

    def parent_of(blind_unique_id: str):
        blind = devices.async_get_device_by_identifier((DOMAIN, blind_unique_id), entry.entry_id)
        return devices.async_get(blind.via_device_id).name

    assert parent_of(f"{CONTROLLER_ID}_abc-01") == "Room: Dining"
    assert parent_of(f"{CONTROLLER_ID}_abc-02") == "Room: Dining"
    assert parent_of(f"{CONTROLLER_ID}_def-01") == "Room: Guest"


async def test_a_blind_whose_room_has_no_device_falls_back_to_the_controller(
    hass: HomeAssistant, entry
) -> None:
    from homeassistant.helpers import device_registry as device_registry_module
    from custom_components.neosmartblinds.cover import NeoSmartCloudCover

    devices = device_registry_module.async_get(hass)
    controller = devices.async_get_device_by_identifier((DOMAIN, CONTROLLER_ID), entry.entry_id)

    blind = NeoSmartCloudCover(
        None,
        {"unique_id": "x", "blind_code": "a-01", "controller_id": CONTROLLER_ID, "name": "X"},
        "user",
        controller.id,
    )

    assert blind.device_info["via_device_id"] == controller.id
