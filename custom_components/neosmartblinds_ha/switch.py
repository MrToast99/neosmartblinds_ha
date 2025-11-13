"""Support for Neo Smart Blinds schedule switches."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .api import NeoSmartCloudAPI, parse_schedules_from_data

_LOGGER = logging.getLogger(__name__)

# Map API commands to friendly names
COMMAND_MAP = {
    "cl": "Close",
    "op": "Open",
    "i1": "Favorite 1",
    "i2": "Favorite 2",
}

# --- ADDED ICON MAP ---
COMMAND_ICON_MAP = {
    "cl": "mdi:arrow-down",
    "op": "mdi:arrow-up",
    "i1": "mdi:numeric-1-circle",
    "i2": "mdi:numeric-2-circle",
}
# --- END ADDED ---

# Map API days to friendly names
DAY_MAP = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds schedule switches."""
    
    entry_data = hass.data[DOMAIN][entry.entry_id]
    cloud_api: NeoSmartCloudAPI = entry_data["api"]
    full_data: dict = entry_data["data"]
    
    schedules = parse_schedules_from_data(full_data)
    
    if not schedules:
        _LOGGER.info("No Neo schedules found to create switches.")
        return

    entities = [
        NeoSmartScheduleSwitch(
            cloud_api=cloud_api,
            schedule_data=schedule,
            account_username=entry.data["username"],
        )
        for schedule in schedules if schedule.get("controller_id")
    ]
    
    async_add_entities(entities)

class NeoSmartScheduleSwitch(SwitchEntity):
    """Representation of a Neo Smart Blind Schedule."""

    def __init__(self, cloud_api: NeoSmartCloudAPI, schedule_data: dict, account_username: str):
        self._cloud_api = cloud_api # Use Cloud API for schedules
        self._schedule_id = schedule_data["id"]
        self._attr_unique_id = f"schedule_{self._schedule_id}"
        self._account_username = account_username
        self._controller_id = schedule_data["controller_id"]
        
        self._room_name = schedule_data["room_name"]
        self._command = schedule_data.get("command", "unknown")
        self._time = schedule_data.get("time", "")
        self._type = schedule_data.get("type", "TIME")
        
        self._attr_name = f"Schedule: {self._room_name} {COMMAND_MAP.get(self._command, self._command)} at {self._time}"
        if self._type == "SUNSET":
            self._attr_name += " (Sunset)"
            
        self._attr_is_on = schedule_data.get("enabled", False)
        
        # --- ADDED ICON LOGIC ---
        self._attr_icon = COMMAND_ICON_MAP.get(self._command)
        # --- END ADDED ---
        
        self._attr_extra_state_attributes = {
            "schedule_id": self._schedule_id,
            "room": self._room_name,
            "command": COMMAND_MAP.get(self._command, self._command),
            "time": self._time,
            "type": self._type,
            "days": self._get_friendly_days(schedule_data.get("days", {})),
        }

    def _get_friendly_days(self, days_dict: dict) -> str:
        """Create a friendly string for days of the week."""
        active_days = [DAY_MAP[day] for day, active in days_dict.items() if active]
        if len(active_days) == 7:
            return "Every day"
        if not active_days:
            return "Never"
        return ", ".join(active_days)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group switches under the controller."""
        return {
            "identifiers": {(DOMAIN, self._controller_id)},
            "name": f"Neo Controller ({self._room_name})",
            "manufacturer": "Neo Smart Blinds",
            "via_device": (DOMAIN, self._account_username),
        }

    async def async_turn_on(self, **kwargs):
        """Enable the schedule."""
        if await self._cloud_api.async_set_schedule_state(self._schedule_id, True):
            self._attr_is_on = True
            self.async_write_ha_state() # <-- This was already correct!
        else:
            _LOGGER.warning("Failed to enable schedule '%s'.", self.name)

    async def async_turn_off(self, **kwargs):
        """Disable the schedule."""
        if await self._cloud_api.async_set_schedule_state(self._schedule_id, False):
            self._attr_is_on = False
            self.async_write_ha_state() # <-- This was already correct!
        else:
            _LOGGER.warning("Failed to disable schedule '%s'.", self.name)