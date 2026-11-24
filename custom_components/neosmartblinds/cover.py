"""Support for Neo Smart Blinds (Cloud) covers."""
import logging
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr

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
from .entity import NeoSmartEntity, async_send_to_blinds
from .models import NeoSmartConfigEntry

_LOGGER = logging.getLogger(__name__)

# Commands go to the Neo cloud one entity at a time.
PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeoSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Neo Smart Blinds cover entities."""
    controller: NeoSmartCloudAPI = entry.runtime_data.api
    full_data: dict = entry.runtime_data.data
    device_registry = dr.async_get(hass)

    entities = []

    # 1. Add individual blinds
    blinds = parse_blinds_from_data(full_data)
    if blinds:
        for blind_data in blinds:
            # A blind sits under its room's device (Controller > Room > Blind). Without
            # one it falls back to the controller.
            parent_device = device_registry.async_get_device_by_identifier(
                (DOMAIN, blind_data["room_unique_id"]), entry.entry_id
            ) or device_registry.async_get_device_by_identifier(
                (DOMAIN, blind_data["controller_id"]), entry.entry_id
            )
            entities.append(
                NeoSmartCloudCover(
                    controller,
                    blind_data,
                    entry.data["username"],
                    parent_device.id if parent_device else None,
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

class NeoSmartCloudCover(NeoSmartEntity, CoverEntity):
    """Representation of an individual Neo Smart Blind (Cloud)."""

    _attr_has_entity_name = True
    _attr_name = None # Inherit name exactly from the Device (e.g., "Master left")
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_assumed_state = True  # No state feedback from device; commands are fire-and-forget

    def __init__(
        self,
        controller: NeoSmartCloudAPI,
        blind_data: dict,
        account_username: str,
        parent_device_id: str | None = None,
    ):
        """Initialize the blind."""
        super().__init__(controller)
        self._attr_unique_id = blind_data["unique_id"]
        self._blind_code = blind_data["blind_code"]
        self._controller_id = blind_data["controller_id"]
        self._motor_code = blind_data.get("motor_code", "unknown")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=blind_data["name"], # The simple name used for the entity
            manufacturer="Neo Smart Blinds",
            model=f"Blind (Motor: {self._motor_code.upper()})",
        )
        if parent_device_id:
            self._attr_device_info["via_device_id"] = parent_device_id

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

    async def _send(self, command: str) -> None:
        """Send a command; raises HomeAssistantError if the cloud didn't take it."""
        await self._controller.async_send_command(
            self._controller_id, self._blind_code, command, self._motor_code
        )

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._send(CMD_DOWN)
        self._attr_is_closed = True
        self._attr_current_cover_position = 0
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._send(CMD_UP)
        self._attr_is_closed = False
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._send(CMD_STOP)
        self._attr_is_closed = None
        self._attr_current_cover_position = None
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Move the blind to a specific position."""
        position = kwargs[ATTR_POSITION]
        # Protocol supports positions 01-99; clamp to valid range
        position = max(1, min(99, position))
        await self._send(str(position).zfill(2))
        self._attr_current_cover_position = position
        self._attr_is_closed = position == 0
        self.async_write_ha_state()

    async def favorite_1(self):
        """Trigger Favorite 1 for this blind."""
        await self._send(CMD_FAV)

    async def favorite_2(self):
        """Trigger Favorite 2 for this blind."""
        await self._send(CMD_FAV2)


class NeoSmartRoomCover(NeoSmartEntity, CoverEntity):
    """Representation of a Room group of Neo Smart Blinds."""

    # The main entity of the room's own device ("Room: Dining"), so it takes that name.
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "room"  # for the icon
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_assumed_state = True  # No state feedback from device; commands are fire-and-forget

    def __init__(self, controller: NeoSmartCloudAPI, room_data: dict):
        """Initialize the room group."""
        super().__init__(controller)
        self._attr_unique_id = room_data["unique_id"]
        self._controller_id = room_data["controller_id"]
        self._blind_codes = room_data["blind_codes"]
        self._motor_codes = room_data.get("motor_codes", {})

        # The room's own device, created at setup (see __init__.py).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)}
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
        """Send a command to all blinds in the room concurrently."""
        await async_send_to_blinds(
            self._controller,
            self._controller_id,
            self._blind_codes,
            self._motor_codes,
            command,
        )

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
