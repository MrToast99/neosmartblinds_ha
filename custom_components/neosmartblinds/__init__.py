"""The Neo Smart Blinds (Cloud) integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client 
from homeassistant.const import CONF_USERNAME, Platform

from homeassistant.helpers import device_registry as dr, entity_platform

from .const import DOMAIN
from .api import (
    NeoSmartCloudAPI, 
    NeoSmartCloudAuthError, 
    parse_controllers_from_data
)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)

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
    device_registry.async_get_or_create(
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
            via_device=(DOMAIN, account_username) 
        )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register Favorite Services
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
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
