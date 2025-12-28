"""Constants for the Neo Smart Blinds (Cloud) integration."""

DOMAIN = "neosmartblinds"

API_BASE_URL = "https://api.neosmartblinds.com"
API_TOKEN_URL = f"{API_BASE_URL}/oauth/token"
API_LOCATION_URL = f"{API_BASE_URL}/location" 

API_COMMAND_URL = f"{API_BASE_URL}/esp32/multi-transmit"
API_SCHEDULE_UPDATE_URL = f"{API_BASE_URL}/location/{{uuid}}/schedules/{{schedule_id}}"

CMD_UP = "up"
CMD_DOWN = "dn"
CMD_STOP = "sp"
CMD_FAV = "i1"
CMD_FAV2 = "i2"
CMD_GP = "gp"

# --- TDBU / TILT COMMANDS ---
CMD_TDBU_MIDDLE_UP = "u4"
CMD_TDBU_MIDDLE_DOWN = "d4"
CMD_TDBU_LOWER_UP = "u2"
CMD_TDBU_LOWER_DOWN = "d2"

CLIENT_ID = "mobile"
