"""The Neo Smart Blinds (Cloud) integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card, async_serve_card, async_unregister_card
from .const import DOMAIN
from .api import (
    NeoSmartCloudAPI,
    NeoSmartCloudAuthError,
    parse_controllers_from_data
)
from .sidebar import async_follow_entries, async_update_sidebar_panel
from .websocket_api import async_register_websocket

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Once per Home Assistant run: the dashboard card's files, websocket command and Lovelace resource."""
    async_register_websocket(hass)
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Neo Smart Blinds (Cloud) from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
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
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        _LOGGER.error("Failed to login and fetch data: %s", err)
        return False
        
    hass.data[DOMAIN][entry.entry_id] = {"api": cloud_api, "data": full_data}

    device_registry = dr.async_get(hass)

    # 1. Create the top-level "Account" device
    account_username = entry.data[CONF_USERNAME]
    account_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, account_username)},
        name=f"Neo Blinds ({account_username})",
        manufacturer="Neo Smart Blinds",
        model="Cloud Account",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    # 2. Create the "Controller" devices
    controllers = parse_controllers_from_data(full_data)
    for controller in controllers:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, controller["id"])},
            name=f"Neo Controller ({controller['room_name']})",
            manufacturer="Neo Smart Blinds",
            model="Cloud Controller",
            via_device_id=account_device.id,
        )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register Favorite Services
    # NOTE: These custom services are largely redundant now that dedicated ButtonEntity
    # classes exist for favorites. Users can call button.press on the favorite button
    # entities in automations instead. Consider removing these in a future version.
    async def handle_favorite(call: ServiceCall):
        """Handle favorite service calls."""
        method = "favorite_1" if call.service == "favorite_1" else "favorite_2"
        platforms = entity_platform.async_get_platforms(hass, DOMAIN)
        
        for platform in platforms:
            if platform.domain == Platform.COVER:
                entities = await platform.async_extract_from_service(call)
                for entity in entities:
                    if hasattr(entity, method):
                        await getattr(entity, method)()

    hass.services.async_register(DOMAIN, "favorite_1", handle_favorite)
    hass.services.async_register(DOMAIN, "favorite_2", handle_favorite)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await async_update_sidebar_panel(hass)
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Clean up registered services if no other config entries remain
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "favorite_1")
            hass.services.async_remove(DOMAIN, "favorite_2")
    # A disabled entry stops asking for the sidebar page; a reloading one still does.
    await async_update_sidebar_panel(hass)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """The entry is being deleted: drop its sidebar page, and the card's resource with the last account."""
    await async_update_sidebar_panel(hass, removed_entry_id=entry.entry_id)
    if not [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]:
        await async_unregister_card(hass)
