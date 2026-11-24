"""Shared pieces for the Neo Smart Blinds entities."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from .api import NeoSmartCloudAPI
from .const import DOMAIN


class NeoSmartEntity(Entity):
    """Base class: entities here are updated by the commands they send, never polled.

    The Neo cloud reports no state, so the only thing that can make an entity unavailable
    is the login being rejected: until the user signs in again, nothing can be controlled.
    """

    _attr_should_poll = False

    def __init__(self, controller: NeoSmartCloudAPI) -> None:
        self._controller = controller

    @property
    def available(self) -> bool:
        return not self._controller.auth_failed

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._controller.async_add_auth_listener(self.async_write_ha_state)
        )


async def async_send_to_blinds(
    controller: NeoSmartCloudAPI,
    controller_id: str,
    blind_codes: Iterable[str],
    motor_codes: Mapping[str, str],
    command: str,
) -> None:
    """Send one command to several blinds at once.

    Every blind is tried even if one fails. If any failed, raises HomeAssistantError so
    the caller doesn't record a state the room never reached.
    """
    codes = list(blind_codes)
    results = await asyncio.gather(
        *(
            controller.async_send_command(
                controller_id, code, command, motor_codes.get(code, "unknown")
            )
            for code in codes
        ),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, Exception):
            raise result  # cancellation and the like must not be swallowed
    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="group_command_failed",
            translation_placeholders={
                "failed": str(len(failures)),
                "total": str(len(codes)),
            },
        ) from failures[0]
