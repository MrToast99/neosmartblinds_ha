"""Tests for the cover, button and switch entities."""
import pytest
from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.neosmartblinds.const import DOMAIN

from conftest import BLIND_1, BLIND_2, ROOM


def entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert found, f"no {domain} entity with unique id {unique_id}"
    return found


def sent(api) -> list[tuple]:
    """(blind code, command, motor) of every command sent so far, in a stable order."""
    return sorted(
        (call.args[1], call.args[2], call.args[3])
        for call in api.async_send_command.await_args_list
    )


async def call(hass: HomeAssistant, domain: str, service: str, entity: str, **data):
    await hass.services.async_call(
        domain, service, {"entity_id": entity, **data}, blocking=True
    )


# --- what gets created -------------------------------------------------------


async def test_every_entity_is_created(hass: HomeAssistant, entry) -> None:
    for domain, unique_id in (
        ("cover", BLIND_1),
        ("cover", BLIND_2),
        ("cover", ROOM),
        ("button", f"{BLIND_1}_fav_1"),
        ("button", f"{BLIND_1}_fav_2"),
        ("button", f"{ROOM}_fav_1"),
        ("button", f"{ROOM}_fav_2"),
        ("switch", "s1"),
    ):
        assert hass.states.get(entity_id(hass, domain, unique_id)), unique_id


async def test_blinds_are_named_after_their_device_and_rooms_read_room(
    hass: HomeAssistant, entry
) -> None:
    def name(domain: str, unique_id: str) -> str:
        return hass.states.get(entity_id(hass, domain, unique_id)).name

    assert name("cover", BLIND_1) == "Slider"
    assert name("cover", ROOM) == "Room: Dining"
    assert name("button", f"{BLIND_1}_fav_1") == "Slider Favorite 1"
    assert name("button", f"{BLIND_1}_fav_2") == "Slider Favorite 2"
    assert name("button", f"{ROOM}_fav_1") == "Room: Dining Favorite 1"
    assert name("button", f"{ROOM}_fav_2") == "Room: Dining Favorite 2"
    assert name("switch", "s1") == "Room: Dining Open at 7:00"


async def test_covers_are_blinds_with_assumed_state(hass: HomeAssistant, entry) -> None:
    for unique_id in (BLIND_1, BLIND_2, ROOM):
        state = hass.states.get(entity_id(hass, "cover", unique_id))
        assert state.attributes["device_class"] == CoverDeviceClass.BLIND
        assert state.attributes["assumed_state"] is True
        assert state.state == STATE_UNKNOWN  # nothing has been sent yet


async def test_position_is_only_offered_to_motors_that_report_it(
    hass: HomeAssistant, entry
) -> None:
    def features(unique_id: str) -> int:
        return hass.states.get(entity_id(hass, "cover", unique_id)).attributes[
            "supported_features"
        ]

    assert features(BLIND_1) & CoverEntityFeature.SET_POSITION
    assert not features(BLIND_2) & CoverEntityFeature.SET_POSITION
    assert not features(ROOM) & CoverEntityFeature.SET_POSITION


# --- one blind -----------------------------------------------------------------


async def test_open_close_stop_one_blind(hass: HomeAssistant, entry, api) -> None:
    cover = entity_id(hass, "cover", BLIND_1)

    await call(hass, "cover", "open_cover", cover)
    assert hass.states.get(cover).state == "open"
    assert hass.states.get(cover).attributes["current_position"] == 100

    await call(hass, "cover", "close_cover", cover)
    assert hass.states.get(cover).state == "closed"
    assert hass.states.get(cover).attributes["current_position"] == 0

    await call(hass, "cover", "stop_cover", cover)
    assert hass.states.get(cover).state == STATE_UNKNOWN

    assert [c.args[1:] for c in api.async_send_command.await_args_list] == [
        ("abc-01", "up", "m1"),
        ("abc-01", "dn", "m1"),
        ("abc-01", "sp", "m1"),
    ]
    assert api.async_send_command.await_args_list[0].args[0] == "ctrl-1"


@pytest.mark.parametrize(("asked", "sent_position"), [(50, "50"), (100, "99"), (3, "03")])
async def test_set_position_stays_inside_what_the_protocol_allows(
    hass: HomeAssistant, entry, api, asked: int, sent_position: str
) -> None:
    cover = entity_id(hass, "cover", BLIND_1)

    await call(hass, "cover", "set_cover_position", cover, position=asked)

    assert api.async_send_command.await_args.args[2] == sent_position
    assert hass.states.get(cover).attributes["current_position"] == int(sent_position)


async def test_a_failed_command_raises_and_keeps_the_old_state(
    hass: HomeAssistant, entry, api
) -> None:
    cover = entity_id(hass, "cover", BLIND_1)
    api.async_send_command.side_effect = HomeAssistantError("cloud said no")

    with pytest.raises(HomeAssistantError):
        await call(hass, "cover", "open_cover", cover)

    assert hass.states.get(cover).state == STATE_UNKNOWN


# --- a room --------------------------------------------------------------------


async def test_room_commands_reach_every_blind_with_its_own_motor(
    hass: HomeAssistant, entry, api
) -> None:
    room = entity_id(hass, "cover", ROOM)

    await call(hass, "cover", "open_cover", room)
    assert hass.states.get(room).state == "open"
    await call(hass, "cover", "close_cover", room)
    assert hass.states.get(room).state == "closed"
    await call(hass, "cover", "stop_cover", room)
    assert hass.states.get(room).state == STATE_UNKNOWN

    assert sent(api) == sorted(
        [
            ("abc-01", "up", "m1"),
            ("abc-02", "up", "m2"),
            ("abc-01", "dn", "m1"),
            ("abc-02", "dn", "m2"),
            ("abc-01", "sp", "m1"),
            ("abc-02", "sp", "m2"),
        ]
    )


async def test_room_with_one_unresponsive_blind_reports_it(
    hass: HomeAssistant, entry, api
) -> None:
    room = entity_id(hass, "cover", ROOM)

    async def flaky(controller_id, code, command, motor):
        if code == "abc-02":
            raise HomeAssistantError("no answer")

    api.async_send_command.side_effect = flaky

    with pytest.raises(HomeAssistantError) as error:
        await call(hass, "cover", "open_cover", room)

    assert error.value.translation_key == "group_command_failed"
    assert error.value.translation_placeholders == {"failed": "1", "total": "2"}
    assert api.async_send_command.await_count == 2  # the other blind was still tried
    assert hass.states.get(room).state == STATE_UNKNOWN


# --- favorites -----------------------------------------------------------------


async def test_blind_favorite_buttons(hass: HomeAssistant, entry, api) -> None:
    await call(hass, "button", "press", entity_id(hass, "button", f"{BLIND_1}_fav_1"))
    await call(hass, "button", "press", entity_id(hass, "button", f"{BLIND_1}_fav_2"))

    assert sent(api) == sorted([("abc-01", "i1", "m1"), ("abc-01", "i2", "m1")])


async def test_room_favorite_buttons_reach_every_blind(
    hass: HomeAssistant, entry, api
) -> None:
    await call(hass, "button", "press", entity_id(hass, "button", f"{ROOM}_fav_2"))

    assert sent(api) == sorted([("abc-01", "i2", "m1"), ("abc-02", "i2", "m2")])


async def test_a_failed_room_favorite_raises(hass: HomeAssistant, entry, api) -> None:
    api.async_send_command.side_effect = HomeAssistantError("cloud said no")

    with pytest.raises(HomeAssistantError):
        await call(hass, "button", "press", entity_id(hass, "button", f"{ROOM}_fav_1"))


@pytest.mark.parametrize(("service", "command"), [("favorite_1", "i1"), ("favorite_2", "i2")])
async def test_favorite_actions_on_blinds_and_rooms(
    hass: HomeAssistant, entry, api, service: str, command: str
) -> None:
    """The actions are registered once at startup and target cover entities."""
    assert hass.services.has_service(DOMAIN, service)

    await hass.services.async_call(
        DOMAIN,
        service,
        {
            "entity_id": [
                entity_id(hass, "cover", BLIND_2),
                entity_id(hass, "cover", ROOM),
            ]
        },
        blocking=True,
    )

    assert sent(api) == sorted(
        [
            ("abc-02", command, "m2"),  # the blind
            ("abc-01", command, "m1"),  # the room, blind 1
            ("abc-02", command, "m2"),  # the room, blind 2
        ]
    )


async def test_favorite_actions_survive_unloading_an_account(
    hass: HomeAssistant, entry
) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "favorite_1")
    assert hass.services.has_service(DOMAIN, "favorite_2")


# --- schedules -----------------------------------------------------------------


async def test_schedule_switch(hass: HomeAssistant, entry, api) -> None:
    switch = entity_id(hass, "switch", "s1")
    assert hass.states.get(switch).state == STATE_ON  # as the cloud reports it

    await call(hass, "switch", "turn_off", switch)
    assert hass.states.get(switch).state == STATE_OFF
    api.async_set_schedule_state.assert_awaited_with("s1", False)

    await call(hass, "switch", "turn_on", switch)
    assert hass.states.get(switch).state == STATE_ON
    api.async_set_schedule_state.assert_awaited_with("s1", True)


async def test_a_failed_schedule_change_keeps_the_old_state(
    hass: HomeAssistant, entry, api
) -> None:
    switch = entity_id(hass, "switch", "s1")
    api.async_set_schedule_state.side_effect = HomeAssistantError("cloud said no")

    with pytest.raises(HomeAssistantError):
        await call(hass, "switch", "turn_off", switch)

    assert hass.states.get(switch).state == STATE_ON


# --- a rejected login ----------------------------------------------------------


async def test_entities_become_unavailable_when_the_login_is_rejected(
    hass: HomeAssistant, entry, api
) -> None:
    ids = [
        entity_id(hass, "cover", BLIND_1),
        entity_id(hass, "cover", ROOM),
        entity_id(hass, "button", f"{ROOM}_fav_1"),
        entity_id(hass, "switch", "s1"),
    ]
    assert all(hass.states.get(e).state != STATE_UNAVAILABLE for e in ids)

    api.reject_login()
    await hass.async_block_till_done()

    assert all(hass.states.get(e).state == STATE_UNAVAILABLE for e in ids)


async def test_unloading_stops_listening_for_a_rejected_login(
    hass: HomeAssistant, entry, api
) -> None:
    assert api._listeners  # every entity is listening

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not api._listeners

