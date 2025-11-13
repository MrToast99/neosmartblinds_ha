"""Config flow for Neo Smart Blinds (Cloud)."""
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client 

from .const import DOMAIN
from .api import NeoSmartCloudAPI, NeoSmartCloudAuthError

_LOGGER = logging.getLogger(__name__)

class NeoSmartCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
                api = NeoSmartCloudAPI(self.hass, user_input, client)
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