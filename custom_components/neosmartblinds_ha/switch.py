"""Support for Neo Smart Blinds (Cloud) schedule switches."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import NeoSmartCloudAPI, parse_schedules_from_data

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds schedule switches."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    controller: NeoSmartCloudAPI = entry_data["api"]
    full_data: dict = entry_data["data"]
    
    schedules = parse_schedules_from_data(full_data)
    if not schedules:
        _LOGGER.info("Schedule setup: No schedules found.")
        return

    entities = [
        NeoSmartScheduleSwitch(
            controller=controller,
            schedule_data=schedule,
            account_username=entry.data["username"]
        )
        for schedule in schedules
    ]
    async_add_entities(entities)

class NeoSmartScheduleSwitch(SwitchEntity):
    """Representation of a Neo Smart Blind Schedule Switch."""

    # This tells HA that the switch's name should be
    # <Device Name> <Entity Name> (e.g., "Dining Controller" "Morning")
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, controller: NeoSmartCloudAPI, schedule_data: dict, account_username: str):
        """Initialize the schedule switch."""
        self._controller = controller
        self._schedule_id = schedule_data["id"]
        self._controller_id = schedule_data["controller_id"]
        self._room_name = schedule_data.get("room_name", "Unknown")
        
        self._attr_unique_id = self._schedule_id
        self._attr_name = schedule_data.get("name", f"Schedule {self._schedule_id}")
        self._attr_is_on = schedule_data.get("enabled", False)

        #
        # --- THIS ATTACHES THE SWITCH TO THE CONTROLLER DEVICE ---
        #
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._controller_id)}, # ID'd by the Controller
            name=f"Neo Controller ({self._room_name})",
            manufacturer="Neo Smart Blinds",
            model="Cloud Controller",
            via_device=(DOMAIN, account_username) # Links to the "Account"
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
        if await self._controller.async_set_schedule_state(self._schedule_id, True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the schedule."""
        if await self._controller.async_set_schedule_state(self._schedule_id, False):
            self._attr_is_on = False
            self.async_write_ha_state()
