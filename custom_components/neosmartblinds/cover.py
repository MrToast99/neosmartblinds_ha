"""Support for Neo Smart Blinds (Cloud) covers."""
import logging
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, 
    CMD_UP, 
    CMD_DOWN, 
    CMD_STOP
)
from .api import NeoSmartCloudAPI, parse_blinds_from_data

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds cover entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    controller: NeoSmartCloudAPI = entry_data["api"]
    full_data: dict = entry_data["data"]
    
    blinds = parse_blinds_from_data(full_data)
    if not blinds:
        _LOGGER.warning("Cover setup: No blinds found.")
        return

    entities = [
        NeoSmartCloudCover(
            controller=controller,
            blind_data=blind_data,
            account_username=entry.data["username"],
        )
        for blind_data in blinds
    ]
    async_add_entities(entities)

class NeoSmartCloudCover(CoverEntity):
    """Representation of a Neo Smart Blind (Cloud)."""
    
    _attr_has_entity_name = False 

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict, account_username: str):
        self._controller = controller
        self._attr_unique_id = blind_data["unique_id"] # e.g., vkoYKvLYU7qx_109.055-03
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"] # e.g., vkoYKvLYU7qx
        self._motor_code = blind_data.get("motor_code", "unknown")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)}, # ID'd by the blind itself
            name=blind_data["name"], # e.g., "Master left"
            manufacturer="Neo Smart Blinds",
            model=f"Blind (Motor: {self._motor_code.upper()})",
            # This links it "via" the parent controller device
            # This is the line that was failing, but will now work.
            via_device=(DOMAIN, self._controller_id) 
        )
        
        self._extra_attributes = {
            "room_name": blind_data.get("room_name", "Unknown"),
            "blind_code": self._blind_code,
            "controller_id": self._controller_id,
            "motor_code": self._motor_code,
            "is_tdbu": blind_data.get("is_tdbu", False),
        }
     
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )
             
        if blind_data["has_percent"]:
             features |= CoverEntityFeature.SET_POSITION
             
        self._attr_supported_features = features
        self._attr_is_closed = None
        self._attr_current_cover_position = None
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_attributes

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_DOWN):
            self._attr_is_closed = True
            self._attr_current_cover_position = 0
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_UP):
            self._attr_is_closed = False
            self._attr_current_cover_position = 100
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        if await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_STOP):
            self._attr_is_closed = None
            self._attr_current_cover_position = None
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the blind to a specific position."""
        position = kwargs[ATTR_POSITION]
        
        if self._motor_code in ["no", "db", "ra", "rb", "ap", "bl", "mb", "jo"]:
            position_cmd = str(position).zfill(2)
            await self._controller.async_send_command(self._controller_id, self._blind_code, position_cmd)
        else:
             _LOGGER.warning("Percentage-based positioning is not supported by motor code %s", self._motor_code)
