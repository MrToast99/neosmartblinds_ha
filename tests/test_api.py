"""Tests for the Neo cloud client: signing in, refreshing, errors and the data parsers."""
import base64
import json
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError

from custom_components.neosmartblinds import api as api_module
from custom_components.neosmartblinds.api import (
    NeoSmartCloudAPI,
    NeoSmartCloudAuthError,
    _get_friendly_command_name,
    _sanitize_payload,
    parse_blinds_from_data,
    parse_controllers_from_data,
    parse_rooms_from_data,
    parse_schedules_from_data,
)
from custom_components.neosmartblinds.const import (
    API_AUTHORIZE_NATIVE_URL,
    API_COMMAND_URL,
    API_LOCATION_URL,
    API_SCHEDULE_UPDATE_URL,
    API_TOKEN_URL,
    DOMAIN,
)

from conftest import SAMPLE_DATA

UUID = "user-uuid"
CONTROLLER = "ctrl-1"
CONTROLLER_STRING = f"{CONTROLLER},secret-part"


def jwt(**claims) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def tokens(access: str | None = None, refresh: str = "refresh-1") -> dict:
    return {
        "access_token": access or jwt(usr=UUID, ctrv2=[CONTROLLER_STRING]),
        "refresh_token": refresh,
    }


@pytest.fixture
def mock_cloud():
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http_client:
        yield http_client


def make_api(client: httpx.AsyncClient, **options) -> NeoSmartCloudAPI:
    return NeoSmartCloudAPI(
        MagicMock(),
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
        client,
        options=options,
    )


def allow_login(router, **token_overrides) -> None:
    router.post(API_AUTHORIZE_NATIVE_URL).respond(json={"code": "auth-code"})
    router.post(API_TOKEN_URL).respond(json=tokens(**token_overrides))


async def logged_in(client, router, **options) -> NeoSmartCloudAPI:
    allow_login(router)
    api = make_api(client, **options)
    await api.async_login()
    return api


# --- signing in -----------------------------------------------------------------


async def test_login_stores_the_user_and_the_controllers(mock_cloud, client) -> None:
    allow_login(mock_cloud)
    api = make_api(client)

    await api.async_login()

    assert api.get_user_uuid() == UUID
    assert api._controller_map == {CONTROLLER: CONTROLLER_STRING}
    assert api.auth_failed is False


async def test_login_sends_the_credentials_and_a_pkce_challenge(
    mock_cloud, client
) -> None:
    allow_login(mock_cloud)
    await make_api(client).async_login()

    authorize = json.loads(mock_cloud.calls[0].request.content)
    assert authorize["username"] == "user@example.com"
    assert authorize["password"] == "secret"
    assert authorize["code_challenge_method"] == "S256"
    token_request = mock_cloud.calls[1].request.content.decode()
    assert "code_verifier=" in token_request
    assert "code=auth-code" in token_request


@pytest.mark.parametrize("status", [400, 401, 403, 422])
async def test_login_refused_is_an_auth_error(mock_cloud, client, status) -> None:
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(status)

    with pytest.raises(NeoSmartCloudAuthError):
        await make_api(client).async_login()


async def test_login_server_error_is_not_an_auth_error(mock_cloud, client) -> None:
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(503)

    with pytest.raises(httpx.HTTPStatusError):
        await make_api(client).async_login()


async def test_login_without_a_connection_raises_the_connection_error(
    mock_cloud, client
) -> None:
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(httpx.ConnectError):
        await make_api(client).async_login()


async def test_login_without_an_authorization_code(mock_cloud, client) -> None:
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(json={})

    with pytest.raises(NeoSmartCloudAuthError, match="missing code"):
        await make_api(client).async_login()


async def test_login_without_tokens(mock_cloud, client) -> None:
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(json={"code": "c"})
    mock_cloud.post(API_TOKEN_URL).respond(json={"access_token": "only-this"})

    with pytest.raises(NeoSmartCloudAuthError, match="missing tokens"):
        await make_api(client).async_login()


async def test_login_with_a_token_that_has_no_user(mock_cloud, client) -> None:
    allow_login(mock_cloud, access=jwt(ctrv2=[CONTROLLER_STRING]))

    with pytest.raises(NeoSmartCloudAuthError, match="user UUID"):
        await make_api(client).async_login()


async def test_a_token_that_is_not_a_token_is_ignored(client) -> None:
    assert make_api(client)._decode_token("not-a-jwt", "usr") is None


async def test_a_token_without_controllers_still_logs_in(mock_cloud, client) -> None:
    allow_login(mock_cloud, access=jwt(usr=UUID))
    api = make_api(client)

    await api.async_login()

    assert api._controller_map == {}


# --- refreshing -----------------------------------------------------------------


async def test_refresh_swaps_in_the_new_tokens(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.post(API_TOKEN_URL).respond(json=tokens(refresh="refresh-2"))

    assert await api.async_refresh_token() is True
    assert api._refresh_token == "refresh-2"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401),
        httpx.Response(200, json={"access_token": "no refresh token"}),
        httpx.Response(200, json=tokens(access=jwt(ctrv2=[]))),  # no user in the token
    ],
)
async def test_a_refresh_that_does_not_work_returns_false(
    mock_cloud, client, response
) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.post(API_TOKEN_URL).mock(return_value=response)

    assert await api.async_refresh_token() is False


# --- authenticated requests -----------------------------------------------------


async def test_a_request_signs_in_first_when_needed(mock_cloud, client) -> None:
    allow_login(mock_cloud)
    mock_cloud.get(f"{API_LOCATION_URL}/{UUID}").respond(json=SAMPLE_DATA)
    api = make_api(client)
    api._user_uuid = UUID

    assert await api.async_get_data() == SAMPLE_DATA

    request = mock_cloud.calls.last.request
    assert request.headers["Authorization"].startswith("Bearer ")
    assert request.headers["Origin"] == "https://app.neosmartblinds.com"


@pytest.mark.parametrize("level", ["Enable Full Payload Debug Logging", "No Payload Logging"])
async def test_get_data_logs_according_to_the_chosen_level(
    mock_cloud, client, caplog, level
) -> None:
    api = await logged_in(client, mock_cloud, debug_logging_level=level)
    mock_cloud.get(f"{API_LOCATION_URL}/{UUID}").respond(json=SAMPLE_DATA)

    with caplog.at_level(logging.DEBUG, logger=api_module.__name__):
        await api.async_get_data()

    full = "UNREDACTED" in caplog.text
    assert full is (level == "Enable Full Payload Debug Logging")


async def test_an_expired_token_is_refreshed_and_the_request_repeated(
    mock_cloud, client
) -> None:
    api = await logged_in(client, mock_cloud)
    route = mock_cloud.get(f"{API_LOCATION_URL}/{UUID}")
    route.side_effect = [httpx.Response(401), httpx.Response(200, json=SAMPLE_DATA)]
    mock_cloud.post(API_TOKEN_URL).respond(json=tokens(refresh="refresh-2"))

    assert await api.async_get_data() == SAMPLE_DATA
    assert route.call_count == 2
    assert api.auth_failed is False


async def test_when_refreshing_fails_it_signs_in_again_with_the_saved_password(
    mock_cloud, client
) -> None:
    api = await logged_in(client, mock_cloud)
    route = mock_cloud.get(f"{API_LOCATION_URL}/{UUID}")
    route.side_effect = [httpx.Response(401), httpx.Response(200, json=SAMPLE_DATA)]
    # Refreshing is refused, but a full sign-in still works: the password is fine.
    mock_cloud.post(API_TOKEN_URL).side_effect = [
        httpx.Response(401),
        httpx.Response(200, json=tokens()),
    ]

    assert await api.async_get_data() == SAMPLE_DATA
    assert api.auth_failed is False


async def test_a_rejected_password_is_reported_once_and_then_not_retried(
    mock_cloud, client, caplog
) -> None:
    api = await logged_in(client, mock_cloud)
    listener, callback = MagicMock(), MagicMock()
    api.async_add_auth_listener(listener)
    api.auth_failed_callback = callback
    mock_cloud.get(f"{API_LOCATION_URL}/{UUID}").respond(401)
    mock_cloud.post(API_TOKEN_URL).respond(401)  # refresh refused
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(401)  # and so is the password

    with caplog.at_level(logging.WARNING, logger=api_module.__name__):
        with pytest.raises(NeoSmartCloudAuthError):
            await api.async_get_data()

    assert api.auth_failed is True
    listener.assert_called_once_with()
    callback.assert_called_once_with()
    assert caplog.text.count("login was rejected") == 1

    # From here on nothing goes to the cloud, so a wrong password isn't tried again.
    calls = mock_cloud.calls.call_count
    with pytest.raises(NeoSmartCloudAuthError):
        await api.async_get_data()
    assert mock_cloud.calls.call_count == calls
    listener.assert_called_once_with()


async def test_a_listener_can_be_removed(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    listener = MagicMock()
    remove = api.async_add_auth_listener(listener)

    remove()
    remove()  # removing twice is harmless
    api._mark_auth_failed()

    listener.assert_not_called()


async def test_a_server_error_is_passed_on(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.get(f"{API_LOCATION_URL}/{UUID}").respond(500)

    with pytest.raises(httpx.HTTPStatusError):
        await api.async_get_data()
    assert api.auth_failed is False


# --- commands -------------------------------------------------------------------


async def test_a_command_goes_out_with_the_controller_string_and_a_hash(
    mock_cloud, client
) -> None:
    api = await logged_in(client, mock_cloud)
    route = mock_cloud.post(API_COMMAND_URL).respond(200)

    await api.async_send_command(CONTROLLER, "abc-01", "up", "m1")

    (controller_string, commands), = json.loads(route.calls.last.request.content).items()
    assert controller_string == CONTROLLER_STRING
    (command,) = commands
    assert {k: command[k] for k in ("token", "command", "channel", "motor")} == {
        "token": "abc",
        "command": "up",
        "channel": "01",
        "motor": "m1",
    }
    assert len(command["hash"]) == 7


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("Enable Full Payload Debug Logging", "FULL (UNREDACTED)"),
        ("Enable Redacted Payload Debug Logging", "SANITIZED"),
        ("No Payload Logging", "Sending command to"),
    ],
)
async def test_command_logging_follows_the_chosen_level(
    mock_cloud, client, caplog, level, expected
) -> None:
    api = await logged_in(client, mock_cloud, debug_logging_level=level)
    mock_cloud.post(API_COMMAND_URL).respond(200)

    with caplog.at_level(logging.DEBUG, logger=api_module.__name__):
        await api.async_send_command(CONTROLLER, "abc-01", "up", "m1")

    assert expected in caplog.text
    if level != "Enable Full Payload Debug Logging":
        assert CONTROLLER_STRING not in caplog.text  # never logged unless asked for


async def test_a_command_for_an_unknown_controller(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_send_command("someone-elses", "abc-01", "up", "m1")

    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "controller_not_found"


async def test_a_command_for_a_blind_code_that_is_not_a_blind_code(
    mock_cloud, client
) -> None:
    api = await logged_in(client, mock_cloud)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_send_command(CONTROLLER, "no-dash-here-at-all", "up", "m1")

    assert error.value.translation_key == "invalid_blind_code"


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (httpx.Response(500), "HTTP 500"),
        (httpx.Response(404), "HTTP 404"),
        (httpx.ConnectError("down"), "ConnectError"),
    ],
)
async def test_a_command_the_cloud_refuses(mock_cloud, client, failure, reason) -> None:
    api = await logged_in(client, mock_cloud)
    route = mock_cloud.post(API_COMMAND_URL)
    if isinstance(failure, Exception):
        route.mock(side_effect=failure)
    else:
        route.mock(return_value=failure)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_send_command(CONTROLLER, "abc-01", "up", "m1")

    assert error.value.translation_key == "command_failed"
    assert error.value.translation_placeholders == {"reason": reason}


async def test_a_command_with_a_rejected_login(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.post(API_COMMAND_URL).respond(401)
    mock_cloud.post(API_TOKEN_URL).respond(401)
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(401)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_send_command(CONTROLLER, "abc-01", "up", "m1")

    assert error.value.translation_key == "login_rejected"
    assert api.auth_failed is True


# --- schedules ------------------------------------------------------------------


async def test_a_schedule_is_switched(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    route = mock_cloud.post(API_SCHEDULE_UPDATE_URL.format(uuid=UUID, schedule_id="s1")).respond(
        200
    )

    await api.async_set_schedule_state("s1", False)

    assert json.loads(route.calls.last.request.content) == {"enabled": False}


async def test_a_schedule_change_the_cloud_refuses(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.post(API_SCHEDULE_UPDATE_URL.format(uuid=UUID, schedule_id="s1")).respond(500)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_set_schedule_state("s1", True)

    assert error.value.translation_key == "schedule_failed"
    assert error.value.translation_placeholders == {"reason": "HTTP 500"}


async def test_a_schedule_change_with_a_rejected_login(mock_cloud, client) -> None:
    api = await logged_in(client, mock_cloud)
    mock_cloud.post(API_SCHEDULE_UPDATE_URL.format(uuid=UUID, schedule_id="s1")).respond(401)
    mock_cloud.post(API_TOKEN_URL).respond(401)
    mock_cloud.post(API_AUTHORIZE_NATIVE_URL).respond(401)

    with pytest.raises(HomeAssistantError) as error:
        await api.async_set_schedule_state("s1", True)

    assert error.value.translation_key == "login_rejected"


# --- small helpers --------------------------------------------------------------


async def test_the_hash_falls_back_to_a_random_number(client) -> None:
    api = make_api(client)

    with patch.object(api_module.time, "time", side_effect=RuntimeError("clock")):
        value = api._generate_hash()

    assert len(value) == 7 and value.isdigit()


def test_command_names_are_friendly() -> None:
    assert _get_friendly_command_name("up") == "Open"
    assert _get_friendly_command_name("i2") == "Favorite 2"
    assert _get_friendly_command_name("45") == "Position 45%"
    assert _get_friendly_command_name("zz") == "ZZ"


def test_sanitizing_hides_the_controller_token_and_hash() -> None:
    payload = {"ctrl,secret": [{"token": "t", "hash": "h", "command": "up"}]}

    safe = _sanitize_payload(payload)

    assert "ctrl,secret" not in json.dumps(safe)
    assert '"t"' not in json.dumps(safe) and '"h"' not in json.dumps(safe)
    assert "up" in json.dumps(safe)
    assert payload == {"ctrl,secret": [{"token": "t", "hash": "h", "command": "up"}]}


def test_sanitizing_never_raises() -> None:
    assert _sanitize_payload("not a dict") == {"error": "Payload sanitization failed"}


# --- parsers --------------------------------------------------------------------


def test_parsers_read_the_sample_account() -> None:
    blinds = parse_blinds_from_data(SAMPLE_DATA)
    rooms = parse_rooms_from_data(SAMPLE_DATA)

    assert [b["unique_id"] for b in blinds] == ["ctrl-1_abc-01", "ctrl-1_abc-02"]
    assert blinds[1]["is_tdbu"] is True and blinds[0]["has_percent"] is True
    assert rooms[0]["motor_codes"] == {"abc-01": "m1", "abc-02": "m2"}
    assert parse_controllers_from_data(SAMPLE_DATA) == [
        {"id": "ctrl-1", "room_name": "Dining"}
    ]
    (schedule,) = parse_schedules_from_data(SAMPLE_DATA)
    assert schedule["name"] == "Dining Open at 7:00"
    assert schedule["label"] == "Open at 7:00"  # the name without the room
    assert schedule["controller_id"] == "ctrl-1"
    assert schedule["room_unique_id"] == parse_rooms_from_data(SAMPLE_DATA)[0]["unique_id"]


def test_parsers_cope_with_an_empty_account() -> None:
    for parse in (
        parse_blinds_from_data,
        parse_rooms_from_data,
        parse_controllers_from_data,
        parse_schedules_from_data,
    ):
        assert parse({}) == []


def test_rooms_without_a_controller_or_blinds_are_skipped() -> None:
    data = {
        "rooms": {
            "no-controller": {"name": "A", "token": "t", "blinds": {"1": {"name": "x"}}},
            "no-token": {"name": "B", "controller": "c", "blinds": {"1": {"name": "x"}}},
            "empty": {"name": "C", "controller": "c", "token": "t", "blinds": {"1": None}},
        }
    }

    assert parse_blinds_from_data(data) == []
    assert parse_rooms_from_data(data) == []


def test_a_schedule_for_an_unknown_room_is_still_listed() -> None:
    data = {"rooms": {}, "schedules": {"s9": {"room": "gone", "time": "1:00", "command": "dn"}}}

    (schedule,) = parse_schedules_from_data(data)

    assert schedule["name"] == "Unknown Room Close at 1:00"
    assert schedule["label"] == "Close at 1:00"
    assert "controller_id" not in schedule
    assert "room_unique_id" not in schedule


def test_a_schedule_that_cannot_be_parsed_keeps_a_fallback_name() -> None:
    data = {"rooms": {}, "schedules": {"s9": {"room": None, "time": "1:00", "command": 5}}}

    (schedule,) = parse_schedules_from_data(data)

    assert schedule["name"] == "Schedule s9"
    assert schedule["label"] == "Schedule s9"
