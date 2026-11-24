"""Shared pieces for the Neo Smart Blinds entities."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from .api import NeoSmartCloudAPI


class NeoSmartEntity(Entity):
    """Base class: entities here are updated by the commands they send, never polled."""

    _attr_should_poll = False

    def __init__(self, controller: NeoSmartCloudAPI) -> None:
        self._controller = controller


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
            f"{len(failures)} of {len(codes)} blinds did not respond: {failures[0]}"
        ) from failures[0]
