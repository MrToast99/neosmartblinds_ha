"""Support for Neo Smart Blinds (Cloud) buttons."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, 
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
    """Set up the Neo Smart Blinds buttons."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    controller: NeoSmartCloudAPI = entry_data["api"]
    full_data: dict = entry_data["data"]
    
    entities = []
    
    # 1. Add Favorite buttons for individual blinds
    blinds = parse_blinds_from_data(full_data)
    for blind_data in blinds:
        entities.append(NeoSmartBlindFavoriteButton(controller, blind_data, 1))
        entities.append(NeoSmartBlindFavoriteButton(controller, blind_data, 2))
        
    # 2. Add Favorite buttons for Room groups
    rooms = parse_rooms_from_data(full_data)
    for room_data in rooms:
        entities.append(NeoSmartRoomFavoriteButton(controller, room_data, 1))
        entities.append(NeoSmartRoomFavoriteButton(controller, room_data, 2))
        
    async_add_entities(entities)


class NeoSmartBlindFavoriteButton(ButtonEntity):
    """Favorite button for an individual blind."""
    
    _attr_has_entity_name = True

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict, fav_number: int):
        """Initialize the button."""
        self._controller = controller
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._fav_number = fav_number
        self._command = CMD_FAV if fav_number == 1 else CMD_FAV2
        
        self._attr_unique_id = f"{blind_data['unique_id']}_fav_{fav_number}"
        self._attr_name = f"Favorite {fav_number}"
        
        # DISTINCTION: Solid star for 1, Star-Check for 2
        self._attr_icon = "mdi:star" if fav_number == 1 else "mdi:star-check"
        
        # Link to the blind device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, blind_data["unique_id"])}
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._controller.async_send_command(
            self._controller_id, 
            self._blind_code, 
            self._command
        )


class NeoSmartRoomFavoriteButton(ButtonEntity):
    """Favorite button for a Room group."""
    
    # Show exactly as "Room: Dining Favorite 1"
    _attr_has_entity_name = False 

    def __init__(self, controller: NeoSmartCloudAPI, room_data: dict, fav_number: int):
        """Initialize the room favorite button."""
        self._controller = controller
        self._controller_id = room_data["controller_id"]
        self._blind_codes = room_data["blind_codes"]
        self._fav_number = fav_number
        self._command = CMD_FAV if fav_number == 1 else CMD_FAV2
        
        self._attr_unique_id = f"{room_data['unique_id']}_fav_{fav_number}"
        self._attr_name = f"{room_data['name']} Favorite {fav_number}"
        
        # Room-specific favorite icons
        self._attr_icon = "mdi:star-settings" if fav_number == 1 else "mdi:star-cog"
        
        # Link to the Controller device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._controller_id)}
        )

    async def async_press(self) -> None:
        """Handle the button press for the entire room."""
        _LOGGER.debug(
            "Triggering Favorite %s for all blinds in room: %s", 
            self._fav_number, self._attr_name
        )
        for code in self._blind_codes:
            await self._controller.async_send_command(
                self._controller_id, 
                code, 
                self._command
            )
