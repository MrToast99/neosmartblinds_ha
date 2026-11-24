"""Runtime data kept on each Neo Smart Blinds config entry."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .api import NeoSmartCloudAPI


@dataclass
class NeoSmartRuntimeData:
    """What a loaded account needs: the API client and the data read at setup."""

    api: NeoSmartCloudAPI
    data: dict


type NeoSmartConfigEntry = ConfigEntry[NeoSmartRuntimeData]
