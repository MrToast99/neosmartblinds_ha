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
    CMD_STOP,
    CMD_FAV,
    CMD_FAV2
)
from .api import (
    NeoSmartCloudAPI, 
    parse_blinds_from_data, 
    parse_rooms_from_data
)

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
    
    entities = []
    
    # 1. Add individual blinds
    blinds = parse_blinds_from_data(full_data)
    if blinds:
        for blind_data in blinds:
            entities.append(
                NeoSmartCloudCover(
                    controller, 
                    blind_data, 
                    entry.data["username"]
                )
            )
        
    # 2. Add room groups
    rooms = parse_rooms_from_data(full_data)
    if rooms:
        for room_data in rooms:
            entities.append(
                NeoSmartRoomCover(
                    controller, 
                    room_data
                )
            )
        
    if entities:
        async_add_entities(entities)

class NeoSmartCloudCover(CoverEntity):
    """Representation of an individual Neo Smart Blind (Cloud)."""
    
    _attr_has_entity_name = True 
    _attr_name = None # Inherit name exactly from the Device (e.g., "Master left")

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict, account_username: str):
        """Initialize the blind."""
        self._controller = controller
        self._attr_unique_id = blind_data["unique_id"]
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._motor_code = blind_data.get("motor_code", "unknown")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=blind_data["name"], # The simple name used for the entity
            manufacturer="Neo Smart Blinds",
            model=f"Blind (Motor: {self._motor_code.upper()})",
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
             
        if blind_data.get("has_percent"):
             features |= CoverEntityFeature.SET_POSITION
             
        self._attr_supported_features = features
        
        # Initial states - prevents AttributeError on startup
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
        position_cmd = str(position).zfill(2)
        
        if await self._controller.async_send_command(self._controller_id, self._blind_code, position_cmd):
            self._attr_current_cover_position = position
            self._attr_is_closed = position == 0
            self.async_write_ha_state()

    async def favorite_1(self):
        """Trigger Favorite 1 for this blind."""
        await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_FAV)

    async def favorite_2(self):
        """Trigger Favorite 2 for this blind."""
        await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_FAV2)


class NeoSmartRoomCover(CoverEntity):
    """Representation of a Room group of Neo Smart Blinds."""
    
    # Disable prefixing so the card shows exactly "Room: Dining"
    _attr_has_entity_name = False 
    _attr_icon = "mdi:google-circles-group"

    def __init__(self, controller: NeoSmartCloudAPI, room_data: dict):
        """Initialize the room group."""
        self._controller = controller
        self._attr_unique_id = room_data["unique_id"]
        self._attr_name = room_data["name"] # e.g., "Room: Dining"
        self._controller_id = room_data["controller_id"]
        self._blind_codes = room_data["blind_codes"]
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._controller_id)}
        )
        
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )

        # Initial states
        self._attr_is_closed = None
        self._attr_current_cover_position = None

    async def _send_group_command(self, command: str):
        """Send a command to all blinds in the room."""
        for code in self._blind_codes:
            await self._controller.async_send_command(self._controller_id, code, command)

    async def async_open_cover(self, **kwargs):
        """Open all blinds in the room."""
        await self._send_group_command(CMD_UP)
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Close all blinds in the room."""
        await self._send_group_command(CMD_DOWN)
        self._attr_is_closed = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop all blinds in the room."""
        await self._send_group_command(CMD_STOP)
        self._attr_is_closed = None
        self.async_write_ha_state()

    async def favorite_1(self):
        """Trigger Favorite 1 for all blinds in the room."""
        await self._send_group_command(CMD_FAV)
        self._attr_is_closed = None
        self.async_write_ha_state()

    async def favorite_2(self):
        """Trigger Favorite 2 for all blinds in the room."""
        await self._send_group_command(CMD_FAV2)
        self._attr_is_closed = None
        self.async_write_ha_state()
