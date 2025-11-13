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

from .const import (
    DOMAIN, 
    CMD_UP, 
    CMD_DOWN, 
    CMD_STOP,
    CMD_FAV,
    CMD_FAV2,
    CMD_GP
    # TDBU commands are not used by the cover entity card,
    # so we don't need to import them here.
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
        _LOGGER.warning("No blinds found on Neo Smart Blinds account.")
        return

    entities = [
        NeoSmartCloudCover(
            controller=controller, # <-- Pass the CLOUD controller
            blind_data=blind_data,
            account_username=entry.data["username"],
        )
        for blind_data in blinds
    ]
    
    async_add_entities(entities)

class NeoSmartCloudCover(CoverEntity):
    """Representation of a Neo Smart Blind (Cloud)."""

    def __init__(self, controller: NeoSmartCloudAPI, blind_data: dict, account_username: str):
        self._controller = controller # This is now the CloudAPI
        self._attr_unique_id = blind_data["unique_id"]
        self._attr_name = blind_data["name"]
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._room_name = blind_data["room_name"]
        self._account_username = account_username
        
        self._motor_code = blind_data.get("motor_code", "unknown")
        self._is_tdbu = blind_data.get("is_tdbu", False)
        
        
        # --- MODIFIED ---
        # We now add the TILT features back, which gives us buttons on the card.
        # We will map these buttons to the Favorite services.
        
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )
        
        # Per PDF, all motors have at least one favorite ('gp' or 'i1')
        # So we add OPEN_TILT and map it to Favorite 1 for ALL blinds.
        features |= CoverEntityFeature.OPEN_TILT # Mapped to Favorite 1
            
        # Per PDF, only 'no' and 'rx' motors have a second favorite ('i2')
        if self._motor_code in ["no", "rx"]:
            features |= CoverEntityFeature.CLOSE_TILT # Mapped to Favorite 2
             
        if blind_data["has_percent"]:
             features |= CoverEntityFeature.SET_POSITION
             
        self._attr_supported_features = features
        # --- END MODIFIED ---

        self._attr_is_closed = None
        self._attr_current_cover_position = None
        
    @property
    def device_info(self):
        """Return device info for grouping."""
        return {
            "identifiers": {(DOMAIN, self._controller_id)},
            "name": f"Neo Controller ({self._room_name})",
            "manufacturer": "Neo Smart Blinds",
            "via_device": (DOMAIN, self._account_username),
        }
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "room_name": self._room_name,
            "blind_code": self._blind_code,
            "controller_id": self._controller_id,
            "motor_code": self._motor_code,
            "is_tdbu": self._is_tdbu,
        }

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

    async def async_open_tilt(self, **kwargs):
        """Handle the TILT open button, now MAPPED TO FAVORITE 1."""
        _LOGGER.debug("Triggering Favorite 1 (via open_tilt button)")
        # This will call the service with the correct i1/gp logic
        await self.async_favorite_1()

    async def async_close_tilt(self, **kwargs):
        """Handle the TILT close button, now MAPPED TO FAVORITE 2."""
        _LOGGER.debug("Triggering Favorite 2 (via close_tilt button)")
        # This will call the service with the correct i2 logic
        await self.async_favorite_2()
            
    async def async_set_cover_position(self, **kwargs):
        """Move the blind to a specific position."""
        position = kwargs[ATTR_POSITION]
        
        # Per PDF, percentage command is XX
        # Note: This is only supported for specific motors.
        if self._motor_code in ["no", "db", "ra", "rb", "ap", "bl", "mb", "jo"]:
            # Format as two digits, e.g., "05" or "80"
            position_cmd = str(position).zfill(2)
            await self._controller.async_send_command(self._controller_id, self._blind_code, position_cmd)
        else:
             _LOGGER.warning("Percentage-based positioning is not supported by motor code %s", self._motor_code)
             
    # --- Service call methods ---
    # These are called by the async_open_tilt/async_close_tilt methods
    # AND by the neosmartblinds_ha.favorite_1 service (which *does* have your icon)
    
    async def async_favorite_1(self):
        """Service call for Favorite 1."""
        # 'i1' is only for 'no' and 'rx' motors
        # 'gp' is for all others
        if self._motor_code in ["no", "rx"]:
            _LOGGER.debug("Sending Favorite 1 (i1) command")
            await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_FAV)
        else:
            _LOGGER.debug("Sending Favorite (gp) command")
            await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_GP)
        
        self.async_write_ha_state()

    async def async_favorite_2(self):
        """Service call for Favorite 2."""
        # 'i2' is only for 'no' and 'rx' motors
        # Other motors do not have a second favorite position.
        if self._motor_code in ["no", "rx"]:
            _LOGGER.debug("Sending Favorite 2 (i2) command")
            await self._controller.async_send_command(self._controller_id, self._blind_code, CMD_FAV2)
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Favorite 2 is not supported by motor code '%s'", self_motor_code)