"""Tests for the config flow: setup, reauthentication and options."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neosmartblinds.api import NeoSmartCloudAuthError
from custom_components.neosmartblinds.config_flow import (
    LOG_LEVEL_FULL,
    LOG_LEVEL_NONE,
    LOG_LEVEL_REDACTED,
)
from custom_components.neosmartblinds.const import CONF_SHOW_SIDEBAR, DOMAIN

USERNAME = "user@example.com"
PASSWORD = "old-password"
NEW_PASSWORD = "new-password"
USER_UUID = "11111111-2222-3333-4444-555555555555"

API_CLASS = "custom_components.neosmartblinds.config_flow.NeoSmartCloudAPI"


@pytest.fixture(autouse=True)
def mock_setup():
    """Don't set the integration up for real (no cloud, no frontend)."""
    with (
        patch("custom_components.neosmartblinds.async_setup", return_value=True),
        patch(
            "custom_components.neosmartblinds.async_setup_entry", return_value=True
        ) as setup_entry,
    ):
        yield setup_entry


@pytest.fixture
def api_class():
    """The Neo cloud client class, replaced by a fake that logs in as USER_UUID."""
    with patch(API_CLASS) as api_class:
        client = api_class.return_value
        client.async_login = AsyncMock(return_value=None)
        client.get_user_uuid.return_value = USER_UUID
        yield api_class


@pytest.fixture
def api(api_class):
    """The fake client instance the flow talks to."""
    return api_class.return_value


def _entry(**overrides) -> MockConfigEntry:
    values = {
        "domain": DOMAIN,
        "data": {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        "unique_id": USER_UUID,
        "title": f"Neo Blinds ({USERNAME})",
    }
    values.update(overrides)
    return MockConfigEntry(**values)


async def _start_user_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


def _defaults(result) -> dict:
    """The default value of each field of a form."""
    return {
        str(key): key.default()
        for key in result["data_schema"].schema
        if key.default is not None and callable(key.default)
    }


# --- initial setup ---------------------------------------------------------


async def test_user_form_is_shown(hass: HomeAssistant, api) -> None:
    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    assert _defaults(result)[CONF_SHOW_SIDEBAR] is True


async def test_user_flow_creates_entry(hass: HomeAssistant, api, mock_setup) -> None:
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Neo Blinds ({USERNAME})"
    # The sidebar choice is an option; the credentials are the only stored data.
    assert result["data"] == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    assert result["options"] == {CONF_SHOW_SIDEBAR: True}
    assert result["result"].unique_id == USER_UUID
    api.async_login.assert_awaited_once()
    mock_setup.assert_awaited_once()


async def test_user_flow_can_turn_the_sidebar_off(hass: HomeAssistant, api) -> None:
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_SHOW_SIDEBAR: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_SHOW_SIDEBAR: False}


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NeoSmartCloudAuthError("bad login"), "invalid_auth"),
        (httpx.ConnectError("no route"), "cannot_connect"),
        (
            httpx.HTTPStatusError(
                "server error",
                request=httpx.Request("POST", "https://api.neosmartblinds.com"),
                response=httpx.Response(503),
            ),
            "cannot_connect",
        ),
        (RuntimeError("anything else"), "cannot_connect"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant, api, error: Exception, reason: str
) -> None:
    api.async_login.side_effect = error
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    # The same form can be submitted again once the problem is gone.
    api.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_without_a_user_id_is_an_auth_error(
    hass: HomeAssistant, api
) -> None:
    api.get_user_uuid.return_value = None
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_the_same_account_cannot_be_added_twice(hass: HomeAssistant, api) -> None:
    _entry().add_to_hass(hass)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- reauthentication ------------------------------------------------------


async def _start_reauth(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    return await entry.start_reauth_flow(hass)


async def test_reauth_updates_the_password(
    hass: HomeAssistant, api, mock_setup
) -> None:
    entry = _entry()
    result = await _start_reauth(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == USERNAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_USERNAME: USERNAME, CONF_PASSWORD: NEW_PASSWORD}
    # The entry reloads so it signs in with the new password.
    mock_setup.assert_awaited()


async def test_reauth_checks_the_new_password_with_the_saved_username(
    hass: HomeAssistant, api, api_class
) -> None:
    result = await _start_reauth(hass, _entry())
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )

    # NeoSmartCloudAPI(hass, credentials, client, options=...)
    credentials = api_class.call_args.args[1]
    assert credentials == {CONF_USERNAME: USERNAME, CONF_PASSWORD: NEW_PASSWORD}


async def test_reauth_wrong_password_can_be_retried(hass: HomeAssistant, api) -> None:
    entry = _entry()
    result = await _start_reauth(hass, entry)

    api.async_login.side_effect = NeoSmartCloudAuthError("bad login")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "typo"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD  # nothing saved yet

    api.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == NEW_PASSWORD


async def test_reauth_cannot_connect(hass: HomeAssistant, api) -> None:
    entry = _entry()
    result = await _start_reauth(hass, entry)

    api.async_login.side_effect = httpx.ConnectError("no route")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_PASSWORD] == PASSWORD


async def test_reauth_rejects_a_different_account(hass: HomeAssistant, api) -> None:
    entry = _entry()
    result = await _start_reauth(hass, entry)

    api.get_user_uuid.return_value = "99999999-0000-0000-0000-000000000000"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data[CONF_PASSWORD] == PASSWORD


# --- reconfigure -----------------------------------------------------------


async def _start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    return await entry.start_reconfigure_flow(hass)


async def test_reconfigure_form_offers_the_saved_email_but_not_the_password(
    hass: HomeAssistant, api
) -> None:
    result = await _start_reconfigure(hass, _entry())

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert suggested == {CONF_USERNAME: USERNAME}


async def test_reconfigure_changes_the_email_and_password(
    hass: HomeAssistant, api, mock_setup
) -> None:
    entry = _entry()
    result = await _start_reconfigure(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new@example.com", CONF_PASSWORD: NEW_PASSWORD},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_USERNAME: "new@example.com", CONF_PASSWORD: NEW_PASSWORD}
    assert entry.title == "Neo Blinds (new@example.com)"
    mock_setup.assert_awaited()


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NeoSmartCloudAuthError("bad login"), "invalid_auth"),
        (httpx.ConnectError("no route"), "cannot_connect"),
    ],
)
async def test_reconfigure_errors_can_be_retried(
    hass: HomeAssistant, api, error: Exception, reason: str
) -> None:
    entry = _entry()
    result = await _start_reconfigure(hass, entry)
    login = {CONF_USERNAME: "new@example.com", CONF_PASSWORD: NEW_PASSWORD}

    api.async_login.side_effect = error
    result = await hass.config_entries.flow.async_configure(result["flow_id"], login)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert entry.data[CONF_USERNAME] == USERNAME  # nothing saved
    # What was typed stays in the form, so only the password has to be re-entered.
    typed = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description
    }
    assert typed == {CONF_USERNAME: "new@example.com"}

    api.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], login)
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_rejects_a_different_account(hass: HomeAssistant, api) -> None:
    entry = _entry()
    result = await _start_reconfigure(hass, entry)

    api.get_user_uuid.return_value = "99999999-0000-0000-0000-000000000000"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "other@example.com", CONF_PASSWORD: NEW_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data == {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}


# --- options ---------------------------------------------------------------


async def test_options_form_defaults_for_an_existing_entry(
    hass: HomeAssistant, api
) -> None:
    entry = _entry()  # no options stored: an account from before the options existed
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    defaults = _defaults(result)
    assert defaults[CONF_SHOW_SIDEBAR] is False
    assert defaults["debug_logging_level"] == LOG_LEVEL_REDACTED


async def test_options_are_saved(hass: HomeAssistant, api) -> None:
    entry = _entry(options={CONF_SHOW_SIDEBAR: False})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SHOW_SIDEBAR: True, "debug_logging_level": LOG_LEVEL_NONE},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SHOW_SIDEBAR: True,
        "debug_logging_level": LOG_LEVEL_NONE,
    }


async def test_options_show_the_saved_values(hass: HomeAssistant, api) -> None:
    entry = _entry(
        options={CONF_SHOW_SIDEBAR: True, "debug_logging_level": LOG_LEVEL_FULL}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    defaults = _defaults(result)
    assert defaults[CONF_SHOW_SIDEBAR] is True
    assert defaults["debug_logging_level"] == LOG_LEVEL_FULL
