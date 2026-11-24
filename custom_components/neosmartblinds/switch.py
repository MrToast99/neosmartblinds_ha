"""Support for Neo Smart Blinds (Cloud) schedule switches."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import NeoSmartCloudAPI, parse_rooms_from_data, parse_schedules_from_data
from .entity import NeoSmartEntity
from .models import NeoSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Changes go to the Neo cloud one entity at a time.
PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds schedule switches."""
    controller: NeoSmartCloudAPI = entry.runtime_data.api
    full_data: dict = entry.runtime_data.data
    
    schedules = parse_schedules_from_data(full_data)
    if not schedules:
        _LOGGER.info("Schedule setup: No schedules found.")
        return

    # Schedules sit on their room's device. A room with no blinds has no device, so its
    # schedules stay on the controller.
    room_devices = {room["unique_id"] for room in parse_rooms_from_data(full_data)}
    entities = [
        NeoSmartScheduleSwitch(
            controller=controller,
            schedule_data=schedule,
            room_devices=room_devices,
        )
        for schedule in schedules
    ]
    async_add_entities(entities)

class NeoSmartScheduleSwitch(NeoSmartEntity, SwitchEntity):
    """Representation of a Neo Smart Blind Schedule Switch."""

    _attr_has_entity_name = True
    # Only the icon is translated; the name is built from the room, action and time.
    _attr_translation_key = "schedule"

    def __init__(self, controller: NeoSmartCloudAPI, schedule_data: dict, room_devices: set[str]):
        """Initialize the schedule switch."""
        super().__init__(controller)
        self._schedule_id = schedule_data["id"]
        self._controller_id = schedule_data.get("controller_id") # Get from parser
        self._room_name = schedule_data.get("room_name", "Unknown")
        
        self._attr_unique_id = self._schedule_id
        self._attr_is_on = schedule_data.get("enabled", False)

        room_unique_id = schedule_data.get("room_unique_id")
        if room_unique_id in room_devices:
            # On the room's device the name needs no room: "Room: Dining Open at 7:00".
            self._attr_name = schedule_data.get("label")
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, room_unique_id)})
        else:
            self._attr_name = schedule_data.get("name") # Name is now pre-built
            if self._controller_id:
                self._attr_device_info = DeviceInfo(
                    identifiers={(DOMAIN, self._controller_id)}
                )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "schedule_id": self._schedule_id,
            "room_name": self._room_name
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the schedule."""
        await self._controller.async_set_schedule_state(self._schedule_id, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the schedule."""
        await self._controller.async_set_schedule_state(self._schedule_id, False)
        self._attr_is_on = False
        self.async_write_ha_state()
