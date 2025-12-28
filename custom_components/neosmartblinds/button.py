"""Support for Neo Smart Blinds (Cloud) button entities."""
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
from .api import NeoSmartCloudAPI, parse_blinds_from_data

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds button entities from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    controller: NeoSmartCloudAPI = entry_data["api"]
    full_data: dict = entry_data["data"]
    
    blinds = parse_blinds_from_data(full_data)
    if not blinds:
        _LOGGER.warning("Button setup: No blinds found.")
        return

    entities_to_add = []
    for blind_data in blinds:
        if blind_data.get("motor_code") in ["no", "rx"]:
            entities_to_add.append(NeoSmartFavorite1Button(controller, blind_data))
            entities_to_add.append(NeoSmartFavorite2Button(controller, blind_data))
    
    async_add_entities(entities_to_add)

class NeoSmartFavoriteButtonBase(ButtonEntity):
    """Base class for a Neo Smart Blind Favorite Button."""

    _attr_has_entity_name = True

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict):
        """Initialize the base button."""
        self._controller = controller
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._blind_unique_id = blind_data["unique_id"] # Get the blind's ID
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._blind_unique_id)} # Must match cover.py
        )

class NeoSmartFavorite1Button(NeoSmartFavoriteButtonBase):
    """Representation of a Neo Smart Blind "Favorite 1" Button."""
    
    _attr_has_entity_name = True
    _attr_name = "Favorite 1"  # Becomes "[Device Name] Favorite 1"

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict):
        """Initialize the Favorite 1 button."""
        super().__init__(controller, blind_data)
        self._attr_unique_id = f"{self._blind_unique_id}_favorite_1"
        self._attr_name = "Favorite 1"
        self._attr_icon = "mdi:star-outline"

    async def async_press(self) -> None:
        """Handle the button press, sending CMD_FAV ("i1")."""
        _LOGGER.info("Sending Favorite 1 (i1) command to blind %s", self._blind_code)
        await self._controller.async_send_command(
            self._controller_id, self._blind_code, CMD_FAV
        )

class NeoSmartFavorite2Button(NeoSmartFavoriteButtonBase):
    """Representation of a Neo Smart Blind "Favorite 2" Button."""
    
    _attr_has_entity_name = True
    _attr_name = "Favorite 2"  # Becomes "[Device Name] Favorite 2"

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict):
        """Initialize the Favorite 2 button."""
        super().__init__(controller, blind_data)
        self._attr_unique_id = f"{self._blind_unique_id}_favorite_2"
        self._attr_name = "Favorite 2"
        self._attr_icon = "mdi:star"

    async def async_press(self) -> None:
        """Handle the button press, sending CMD_FAV2 ("i2")."""
        _LOGGER.info("Sending Favorite 2 (i2) command to blind %s", self._blind_code)
        await self._controller.async_send_command(
            self._controller_id, self._blind_code, CMD_FAV2
        )
