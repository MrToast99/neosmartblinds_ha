"""Support for Neo Smart Blinds (Cloud) buttons."""
import logging
from homeassistant.components.button import ButtonEntity
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
from .entity import NeoSmartEntity, async_send_to_blinds
from .models import NeoSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Presses go to the Neo cloud one entity at a time.
PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds buttons."""
    controller: NeoSmartCloudAPI = entry.runtime_data.api
    full_data: dict = entry.runtime_data.data
    
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


class NeoSmartBlindFavoriteButton(NeoSmartEntity, ButtonEntity):
    """Favorite button for an individual blind."""
    
    _attr_has_entity_name = True

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict, fav_number: int):
        """Initialize the button."""
        super().__init__(controller)
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._motor_code = blind_data.get("motor_code", "unknown")
        self._fav_number = fav_number
        self._command = CMD_FAV if fav_number == 1 else CMD_FAV2
        
        self._attr_unique_id = f"{blind_data['unique_id']}_fav_{fav_number}"
        # Name and icon come from translations/en.json and icons.json.
        self._attr_translation_key = f"favorite_{fav_number}"

        # Link to the blind device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, blind_data["unique_id"])}
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._controller.async_send_command(
            self._controller_id, 
            self._blind_code, 
            self._command,
            self._motor_code
        )


class NeoSmartRoomFavoriteButton(NeoSmartEntity, ButtonEntity):
    """Favorite button for a Room group."""
    
    _attr_has_entity_name = True

    def __init__(self, controller: NeoSmartCloudAPI, room_data: dict, fav_number: int):
        """Initialize the room favorite button."""
        super().__init__(controller)
        self._controller_id = room_data["controller_id"]
        self._blind_codes = room_data["blind_codes"]
        self._motor_codes = room_data.get("motor_codes", {})
        self._fav_number = fav_number
        self._command = CMD_FAV if fav_number == 1 else CMD_FAV2
        
        self._attr_unique_id = f"{room_data['unique_id']}_fav_{fav_number}"
        self._room_name = room_data["name"]
        # Name and icon come from translations/en.json and icons.json.
        self._attr_translation_key = f"room_favorite_{fav_number}"

        # Link to the room's own device, created at setup (see __init__.py)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, room_data["unique_id"])}
        )

    async def async_press(self) -> None:
        """Handle the button press for the entire room."""
        _LOGGER.debug(
            "Triggering Favorite %s for all blinds in room: %s", 
            self._fav_number, self._room_name
        )
        await async_send_to_blinds(
            self._controller,
            self._controller_id,
            self._blind_codes,
            self._motor_codes,
            self._command,
        )
