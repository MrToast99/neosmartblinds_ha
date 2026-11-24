"""Config flow for Neo Smart Blinds (Cloud)."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client 

from homeassistant.helpers.selector import (
    SelectSelector, 
    SelectSelectorConfig
)

from .const import CONF_SHOW_SIDEBAR, DOMAIN
from .api import NeoSmartCloudAPI, NeoSmartCloudAuthError
from .sidebar import sidebar_enabled

_LOGGER = logging.getLogger(__name__)


LOG_LEVEL_NONE = "No Payload Logging"
LOG_LEVEL_REDACTED = "Enable Redacted Payload Debug Logging"
LOG_LEVEL_FULL = "Enable Full Payload Debug Logging"

LOG_OPTIONS = [
    LOG_LEVEL_NONE,
    LOG_LEVEL_REDACTED,
    LOG_LEVEL_FULL,
]

def _title(username: str) -> str:
    return f"Neo Blinds ({username})"


class NeoSmartCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Neo Smart Blinds (Cloud)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of adding the controller."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            # The sidebar choice is an option, not part of the account's stored data.
            show_sidebar = user_input.get(CONF_SHOW_SIDEBAR, True)
            credentials = {CONF_USERNAME: username, CONF_PASSWORD: password}

            user_uuid, error = await self._async_try_login(credentials)
            if error:
                errors["base"] = error
            else:
                # Aborting for a duplicate account is not a connection error.
                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=_title(username),
                    data=credentials,
                    options={CONF_SHOW_SIDEBAR: show_sidebar},
                )

        # Show the form for the user to enter username and password
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_SHOW_SIDEBAR, default=True): bool,
            }),
            errors=errors,
        )

    async def _async_validate_login(self, credentials: dict) -> str:
        """Sign in with the credentials and return the account's user ID.

        Raises NeoSmartCloudAuthError for a rejected login; anything else is a
        connection problem.
        """
        client = get_async_client(self.hass, verify_ssl=True)
        api = NeoSmartCloudAPI(self.hass, credentials, client, options={})
        await api.async_login()

        user_uuid = api.get_user_uuid()
        if not user_uuid:
            raise NeoSmartCloudAuthError("Could not parse user ID from token")
        return user_uuid

    async def _async_try_login(
        self, credentials: dict[str, str]
    ) -> tuple[str | None, str | None]:
        """Sign in; returns (user_id, None) or (None, the form error to show)."""
        try:
            return await self._async_validate_login(credentials), None
        except NeoSmartCloudAuthError:
            return None, "invalid_auth"
        except Exception:
            _LOGGER.error("Failed to connect to Neo cloud API", exc_info=True)
            return None, "cannot_connect"

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The stored login stopped working (usually a password change)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password and check it before saving."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            credentials = {
                CONF_USERNAME: entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            user_uuid, error = await self._async_try_login(credentials)
            if error:
                errors["base"] = error
            else:
                if entry.unique_id and entry.unique_id != user_uuid:
                    return self.async_abort(reason="wrong_account")
                # Reloads the entry, which signs in with the new password.
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the email or password the account signs in with."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            credentials = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            user_uuid, error = await self._async_try_login(credentials)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_uuid)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry,
                    title=_title(credentials[CONF_USERNAME]),
                    data_updates=credentials,
                )

        # The password is never filled in for the user.
        suggested = {CONF_USERNAME: entry.data[CONF_USERNAME]}
        if user_input is not None:
            suggested = {CONF_USERNAME: user_input[CONF_USERNAME]}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                suggested,
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler.

        OptionsFlow sets self.config_entry itself, so it takes no constructor argument.
        """
        return NeoSmartBlindsOptionsFlow()


class NeoSmartBlindsOptionsFlow(OptionsFlow):
    """Handle an options flow for the integration."""

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
            vol.Required(
                CONF_SHOW_SIDEBAR,
                default=sidebar_enabled(self.config_entry),
            ): bool,
            vol.Optional(
                "debug_logging_level",
                default=current_level
            ): SelectSelector(SelectSelectorConfig(options=LOG_OPTIONS)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )
