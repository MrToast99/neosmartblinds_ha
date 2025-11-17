"""Config flow for Neo Smart Blinds (Cloud)."""
import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client 

from homeassistant.helpers.selector import (
    SelectSelector, 
    SelectSelectorConfig
)

from .const import DOMAIN
from .api import NeoSmartCloudAPI, NeoSmartCloudAuthError

_LOGGER = logging.getLogger(__name__)


LOG_LEVEL_NONE = "No Payload Logging"
LOG_LEVEL_REDACTED = "Enable Redacted Payload Debug Logging"
LOG_LEVEL_FULL = "Enable Full Payload Debug Logging"

LOG_OPTIONS = [
    LOG_LEVEL_NONE,
    LOG_LEVEL_REDACTED,
    LOG_LEVEL_FULL,
]

class NeoSmartCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Neo Smart Blinds (Cloud)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of adding the controller."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                # Test credentials
                client = get_async_client(self.hass, verify_ssl=True)
                
                # Pass empty options dict, as API now expects it
                api = NeoSmartCloudAPI(
                    self.hass, 
                    user_input, 
                    client, 
                    options={}
                )
                await api.async_login()
                
                user_uuid = api.get_user_uuid()
                if not user_uuid:
                     raise NeoSmartCloudAuthError("Could not parse user ID from token")

                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"Neo Blinds ({username})",
                    data=user_input,
                )
                
            except NeoSmartCloudAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.error("Failed to connect to Neo cloud API", exc_info=True)
                errors["base"] = "cannot_connect"

        # Show the form for the user to enter username and password
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow handler."""
        return NeoSmartBlindsOptionsFlow(config_entry)


class NeoSmartBlindsOptionsFlow(OptionsFlow):
    """Handle an options flow for the integration."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize options flow."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Save the user's choices
            return self.async_create_entry(title="", data=user_input)

        # Get the current setting, defaulting to Redacted
        current_level = self.config_entry.options.get(
            "debug_logging_level", LOG_LEVEL_REDACTED 
        )

        options_schema = vol.Schema({
            vol.Optional(
                "debug_logging_level",
                default=current_level
            ): SelectSelector(SelectSelectorConfig(options=LOG_OPTIONS)),
        })
        # --- END OF FIX ---

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )
