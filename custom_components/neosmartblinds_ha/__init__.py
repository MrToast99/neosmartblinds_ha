"""The Neo Smart Blinds (Cloud) integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client 
from homeassistant.const import CONF_USERNAME, Platform

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .api import NeoSmartCloudAPI, NeoSmartCloudAuthError
PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Neo Smart Blinds (Cloud) from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # Create the cloud client
    cloud_client = get_async_client(hass, verify_ssl=True)
    cloud_api = NeoSmartCloudAPI(hass, entry.data, cloud_client)
    
    try:
        await cloud_api.async_login()
        full_data = await cloud_api.async_get_data()
        
    except NeoSmartCloudAuthError as err:
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        _LOGGER.error("Failed to login and fetch data: %s", err)
        return False
        
    # Store the API object and data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": cloud_api,
        "data": full_data
    }

    # Create the parent "Account" device
    account_username = entry.data[CONF_USERNAME]
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, account_username)},
        name=f"Neo Blinds ({account_username})",
        manufacturer="Neo Smart Blinds",
        model="Cloud Account",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok
