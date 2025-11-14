"""API for Neo Smart Blinds (Cloud)."""
import httpx
import logging
import base64
import json
import time
import random # Keep random for a fallback

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN,
    API_TOKEN_URL,
    API_LOCATION_URL,
    API_COMMAND_URL,
    API_SCHEDULE_UPDATE_URL, 
    CLIENT_ID,
    CMD_UP,
    CMD_DOWN,
    CMD_STOP,
    CMD_FAV,
)

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 15.0

#
# --- HELPER FUNCTION FOR SCHEDULE NAMES ---
#
def _get_friendly_command_name(command: str) -> str:
    """Translate a command code to a friendly name."""
    
    # Map from command codes (like in const.py) to names
    cmd_map = {
        "up": "Open",
        "dn": "Close",
        "sp": "Stop",
        "i1": "Favorite 1",
        "i2": "Favorite 2",
        "gp": "Favorite (GP)",
        "cl": "Close", # From your log data
        "u4": "Middle Up",
        "d4": "Middle Down",
        "u2": "Lower Up",
        "d2": "Lower Down"
    }

    friendly_name = cmd_map.get(command)
    if friendly_name:
        return friendly_name
        
    # Check for position command (e.g., "75")
    if command.isdigit():
        return f"Position {command}%"
        
    return command.upper() # Fallback, e.g., "FAV_1"

# --- END HELPER FUNCTION ---


class NeoSmartCloudAuthError(ConfigEntryAuthFailed):
    """Exception for authentication errors."""

class NeoSmartCloudAPI:
    """A client for the Neo Smart Blinds Cloud API."""

    def __init__(self, hass: HomeAssistant, data: dict, client: httpx.AsyncClient):
        """Initialize the API client."""
        self.hass = hass
        self._username = data[CONF_USERNAME]
        self._password = data[CONF_PASSWORD]
        self._access_token = None
        self._refresh_token = None
        self._user_uuid = None 
        self._client = client
        self._controller_map = {} 

    def get_user_uuid(self) -> str | None:
        """Return the user's UUID."""
        return self._user_uuid

    def _decode_token(self, token: str, key: str):
        """Decode a JWT and extract a specific key."""
        try:
            payload_b64 = token.split('.')[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
            payload_data = json.loads(payload_json)
            
            value = payload_data.get(key)
            if not value:
                _LOGGER.error("Token payload did not contain '%s' key", key)
                return None
            return value
            
        except Exception as err:
            _LOGGER.error("Failed to decode token: %s", err)
            return None

    def _generate_hash(self) -> str:
        """
        Generate the 7-digit hash required by the API.
        Per the official documentation: "A simple implementation is taking the last 7 digits
        from time.now() in milliseconds."
        """
        try:
            time_ms = str(int(time.time() * 1000))
            hash_string = time_ms[-7:]
            _LOGGER.debug("Generated hash: %s", hash_string)
            return hash_string
            
        except Exception as err:
            _LOGGER.error("Failed to generate hash: %s", err)
            # Fallback to a simple 7-digit random number if logic fails
            return str(random.randint(1000000, 9999999))

    async def async_login(self) -> None:
        """Log in to the API and store the auth tokens."""
        _LOGGER.debug("Attempting to log in to Neo Smart Blinds cloud")
        
        payload = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "client_id": CLIENT_ID, 
        }
        
        headers = {
            "Origin": "https://app.neosmartblinds.com",
            "Referer": "https://app.neosmartblinds.com/"
        }

        try:
            response = await self._client.post(API_TOKEN_URL, data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if "access_token" not in data or "refresh_token" not in data:
                _LOGGER.error("Login response missing tokens: %s", data)
                raise NeoSmartCloudAuthError("Login failed, response missing tokens")
                
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            
            self._user_uuid = self._decode_token(self._access_token, "usr")
            if not self._user_uuid:
                raise NeoSmartCloudAuthError("Login succeeded, but failed to parse user UUID from token")

            self._parse_controller_map_from_token(self._access_token)
            
            _LOGGER.info("Successfully logged in to Neo cloud")
            
        except httpx.HTTPStatusError as err:
            _LOGGER.error("Login failed: %s", err)
            raise NeoSmartCloudAuthError("Login failed, check credentials")
        except Exception as err:
            _LOGGER.error("Login request failed: %s", err)
            raise

    async def async_refresh_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        _LOGGER.debug("Refreshing Neo cloud access token")
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": CLIENT_ID,
        }
        
        headers = {
            "Origin": "https://app.neosmartblinds.com",
            "Referer": "https://app.neosmartblinds.com/"
        }
        
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as refresh_client:
                response = await refresh_client.post(API_TOKEN_URL, data=payload, headers=headers)
            
            response.raise_for_status()
            data = response.json()
            
            if "access_token" not in data or "refresh_token" not in data:
                _LOGGER.error("Refresh response missing tokens: %s", data)
                return False
                
            self._access_token = data["access_token"]
            self._refresh_token = data["refresh_token"]
            
            self._user_uuid = self._decode_token(self._access_token, "usr")
            if not self._user_uuid:
                return False

            self._parse_controller_map_from_token(self._access_token)
                
            _LOGGER.debug("Successfully refreshed Neo cloud token")
            return True
            
        except Exception:
            _LOGGER.error("Failed to refresh token, re-login required", exc_info=True)
            return False

    async def _api_request(self, method: str, url: str, **kwargs):
        """Make an authenticated API request, handling token refresh."""
        if not self._access_token:
            await self.async_login()
            
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers["Origin"] = "https://app.neosmartblinds.com"
        headers["Referer"] = "https://app.neosmartblinds.com/"
        kwargs["headers"] = headers
            
        try:
            kwargs.setdefault('timeout', REQUEST_TIMEOUT)
            
            response = await self._client.request(method, url, **kwargs)
            if response.status_code == 401:  # Token expired
                _LOGGER.debug("Token expired, attempting refresh")
                if not await self.async_refresh_token():
                    raise NeoSmartCloudAuthError("Token refresh failed")
                
                headers["Authorization"] = f"Bearer {self._access_token}"
                kwargs["headers"] = headers
                
                response = await self._client.request(method, url, **kwargs)
            
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as err:
            _LOGGER.error("API request failed: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("API request failed: %s", err)
            raise

    def _parse_controller_map_from_token(self, access_token: str):
        """Parse the access token to build the controller UUID-to-String map."""
        try:
            controller_strings = self._decode_token(access_token, "ctrv2")
            if not controller_strings:
                _LOGGER.error("Could not parse controller strings (ctrv2) from access token")
                return
                
            for full_string in controller_strings:
                uuid = full_string.split(',')[0]
                self._controller_map[uuid] = full_string
            
            _LOGGER.debug("Built controller map: %s", self._controller_map)

        except Exception as err:
            _LOGGER.error("Failed to parse controller map: %s", err)

    async def async_get_data(self) -> dict:
        """Get all user data (blinds, schedules) from the cloud."""
        
        url = f"{API_LOCATION_URL}/{self._user_uuid}"
        response = await self._api_request("GET", url)
        data = response.json()
        
        # This is the debug line you used, it's great.
        _LOGGER.info("Full API data payload: %s", data)
        
        return data

    async def async_send_command(self, controller_id: str, blind_code: str, command: str) -> bool:
        """Send a command to a specific blind."""
        
        full_id_string = self._controller_map.get(controller_id)
        if not full_id_string:
            _LOGGER.error("No controller string found for UUID %s", controller_id)
            return False
            
        try:
            token, channel = blind_code.split('-')
        except ValueError:
            _LOGGER.error("Invalid blind_code format: %s", blind_code)
            return False
            
        hash_string = self._generate_hash()
        url = API_COMMAND_URL
        
        payload = {
            full_id_string: [
                {
                    "token": token,
                    "command": command,
                    "channel": channel,
                    "motor": "no",
                    "hash": hash_string
                }
            ]
        }

        _LOGGER.info("Sending command to %s with payload: %s", url, payload)

        try:
            await self._api_request("POST", url, json=payload)
            _LOGGER.info("Command sent successfully")
            return True
        except Exception:
            _LOGGER.error("Failed to send command. Payload was: %s", payload, exc_info=True)
            return False

    async def async_set_schedule_state(self, schedule_id: str, enabled: bool) -> bool:
        """Set the enabled state of a schedule."""
        _LOGGER.debug("Setting schedule %s to %s", schedule_id, enabled)
        
        url = API_SCHEDULE_UPDATE_URL.format(uuid=self._user_uuid, schedule_id=schedule_id)
        payload = {"enabled": enabled} 

        try:
            await self._api_request("POST", url, json=payload)
            _LOGGER.info("Schedule state set successfully")
            return True
        except Exception:
            _LOGGER.error("Failed to set schedule state", exc_info=True)
            return False

def parse_blinds_from_data(data: dict) -> list:
    """Parse the blinds list from the full data payload."""
    blinds_list = []
    
    rooms = data.get("rooms", {})
    if not rooms:
        _LOGGER.warning("No rooms found in API response")
        return []

    for room_id, room in rooms.items():
        controller_id = room.get("controller") 
        room_token = room.get("token") 
        room_name = room.get("name")
        
        if not controller_id or not room_token:
            continue
            
        for channel, blind in room.get("blinds", {}).items():
            if not blind: # Skip empty blind slots (like '01': None)
                continue
            
            blind_name = blind.get("name")
            blind_code = f"{room_token}-{channel.zfill(2)}"
            motor_code = blind.get("motorCode", "unknown") 
            is_tdbu = blind.get("tdbu", False) 
            
            blinds_list.append({
                "unique_id": f"{controller_id}_{blind_code}",
                "name": blind_name,
                "room_name": room_name,
                "blind_code": blind_code,
                "controller_id": controller_id,
                "has_percent": blind.get("hasPercent", False),
                "motor_code": motor_code,
                "is_tdbu": is_tdbu,
            })
            
    return blinds_list

def parse_schedules_from_data(data: dict) -> list:
    """Parse the schedules list from the full data payload."""
    schedules_list = []
    
    schedules = data.get("schedules", {})
    rooms = data.get("rooms", {}) # We get the full room list
    if not schedules:
        _LOGGER.info("No schedules found in API response")
        return []

    for schedule_id, schedule in schedules.items():
        
        friendly_name = f"Schedule {schedule_id}" # Start with a fallback
        try:
            schedule_time = schedule.get("time", "Unknown Time")
            schedule_cmd = schedule.get("command", "cmd")
            room_id = schedule.get("room") # This is the link

            room_name = "Unknown Room" # Fallback
            if room_id and room_id in rooms:
                room_name = rooms[room_id].get("name", room_name) # e.g., "Master"
            
            command_name = _get_friendly_command_name(schedule_cmd) # e.g., "Favorite 1"
            friendly_name = f"{room_name} {command_name} at {schedule_time}"
        
        except Exception as e:
            _LOGGER.warning("Could not parse friendly name for schedule %s: %s", schedule_id, e)

        schedule_data = schedule.copy()
        schedule_data["id"] = schedule_id
        
        if room_id and room_id in rooms:
            schedule_data["room_name"] = rooms[room_id].get("name", "Unknown")
            schedule_data["controller_id"] = rooms[room_id].get("controller")
        
        schedule_data["name"] = friendly_name
        schedules_list.append(schedule_data)
            
    return schedules_list

def parse_controllers_from_data(data: dict) -> list:
    """Parse a unique list of controllers from the data payload."""
    controllers = {} # Use a dict to store unique controllers
    rooms = data.get("rooms", {})
    if not rooms:
        _LOGGER.warning("No rooms found, cannot parse controllers.")
        return []

    for room in rooms.values():
        controller_id = room.get("controller")
        
        # We only add the controller once, using the first
        # room name we see as its "representative" name.
        if controller_id and controller_id not in controllers:
            controllers[controller_id] = {
                "id": controller_id,
                "room_name": room.get("name", "Unknown Room")
            }
            
    return list(controllers.values())
