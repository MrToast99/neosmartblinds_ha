"""The Neo Smart Blinds (Cloud) integration."""
import logging
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import CONF_USERNAME, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr, service
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card, async_serve_card, async_unregister_card
from .const import DOMAIN
from .api import (
    NeoSmartCloudAPI,
    NeoSmartCloudAuthError,
    parse_controllers_from_data,
    parse_rooms_from_data,
)
from .models import NeoSmartConfigEntry, NeoSmartRuntimeData
from .sidebar import async_follow_entries, async_update_sidebar_panel
from .websocket_api import async_register_websocket

ACCOUNT_DEVICE_MODEL = "Cloud Account"
PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Once per Home Assistant run: the dashboard card's files, websocket command and Lovelace resource."""
    async_register_websocket(hass)

    # Favorite actions for blind and room covers. Registered once per run, not per account.
    for name in ("favorite_1", "favorite_2"):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            name,
            entity_domain=COVER_DOMAIN,
            schema=None,
            func=name,
        )

    await async_serve_card(hass)
    # The sidebar page follows the config entries, loaded or not (see sidebar.py).
    async_follow_entries(hass)
    await async_update_sidebar_panel(hass)

    if hass.state == CoreState.running:
        await async_register_card(hass)
    else:
        # Lovelace's resource collection isn't reliably there during early boot.
        async def _on_started(_event: Event) -> None:
            await async_register_card(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NeoSmartConfigEntry) -> bool:
    """Set up Neo Smart Blinds (Cloud) from a config entry."""

    cloud_client = get_async_client(hass, verify_ssl=True)
    
    cloud_api = NeoSmartCloudAPI(
        hass=hass, 
        data=entry.data, 
        client=cloud_client,
        options=entry.options
    )
    
    try:
        await cloud_api.async_login()
        full_data = await cloud_api.async_get_data()
    except NeoSmartCloudAuthError as err:
        # Home Assistant starts the reauth flow, which asks for the new password.
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        # The cloud is unreachable or erroring; Home Assistant retries later.
        raise ConfigEntryNotReady(f"Could not reach the Neo cloud: {err}") from err

    # If the password stops working later (for example it was changed in the Neo app),
    # ask for a new one instead of failing every command from now on.
    cloud_api.auth_failed_callback = lambda: entry.async_start_reauth(hass)

    entry.runtime_data = NeoSmartRuntimeData(api=cloud_api, data=full_data)

    device_registry = dr.async_get(hass)

    # 1. Create the top-level "Account" device
    account_username = entry.data[CONF_USERNAME]
    account_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, account_username)},
        name=f"Neo Blinds ({account_username})",
        manufacturer="Neo Smart Blinds",
        model=ACCOUNT_DEVICE_MODEL,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    # 2. Create the "Controller" devices
    controllers = parse_controllers_from_data(full_data)
    controller_devices = {}
    for controller in controllers:
        controller_devices[controller["id"]] = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, controller["id"])},
            name=f"Neo Controller ({controller['room_name']})",
            manufacturer="Neo Smart Blinds",
            model="Cloud Controller",
            via_device_id=account_device.id,
        )
    
    # 3. Create a "Room" device for each room, under the controller that serves it. One
    # controller can serve several rooms, so the room entities (the room cover and its
    # favorite buttons) live on their own device, and are named after it.
    for room in parse_rooms_from_data(full_data):
        controller_device = controller_devices.get(room["controller_id"])
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, room["unique_id"])},
            name=room["name"],
            manufacturer="Neo Smart Blinds",
            model="Room",
            via_device_id=controller_device.id if controller_device else None,
        )

    # The account device is named after the login, so a changed email leaves the old one
    # behind. The controllers now point at the new one, so the old one can go.
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if device.model == ACCOUNT_DEVICE_MODEL and device.id != account_device.id:
            device_registry.async_remove_device(device.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await async_update_sidebar_panel(hass)
    return True

async def async_reload_entry(hass: HomeAssistant, entry: NeoSmartConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: NeoSmartConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # A disabled entry stops asking for the sidebar page; a reloading one still does.
    await async_update_sidebar_panel(hass)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: NeoSmartConfigEntry) -> None:
    """The entry is being deleted: drop its sidebar page, and the card's resource with the last account."""
    await async_update_sidebar_panel(hass, removed_entry_id=entry.entry_id)
    if not [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]:
        await async_unregister_card(hass)
