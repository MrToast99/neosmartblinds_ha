"""Tests for serving the card and registering it as a Lovelace resource."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.neosmartblinds import card
from custom_components.neosmartblinds.card import (
    CARD_URL,
    LOVELACE_DATA,
    MODE_STORAGE,
    async_register_card,
    async_serve_card,
    async_unregister_card,
)

URL = f"{CARD_URL}?v=1.0-abc"


@pytest.fixture
def http(hass: HomeAssistant) -> MagicMock:
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    return hass.http


@pytest.fixture
def extra_url():
    with (
        patch.object(card, "add_extra_js_url") as add,
        patch.object(card, "remove_extra_js_url") as remove,
    ):
        yield SimpleNamespace(add=add, remove=remove)


class FakeResources:
    """The parts of Lovelace's resource collection the integration uses."""

    def __init__(self, items=(), loaded=True) -> None:
        self.items = [dict(item) for item in items]
        self.loaded = loaded
        self.async_load = AsyncMock()
        self.async_create_item = AsyncMock()
        self.async_update_item = AsyncMock()
        self.async_delete_item = AsyncMock()

    def async_items(self):
        return self.items


def use_lovelace(hass: HomeAssistant, resources: FakeResources | None, mode=MODE_STORAGE):
    if resources is not None:
        hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode=mode, resources=resources)


# --- serving the file --------------------------------------------------------------


async def test_the_card_folder_is_served_once(hass: HomeAssistant, http) -> None:
    first = await async_serve_card(hass)
    second = await async_serve_card(hass)

    assert first == second
    assert first.startswith(f"{CARD_URL}?v=")
    http.async_register_static_paths.assert_awaited_once()
    (config,) = http.async_register_static_paths.await_args.args[0]
    assert config.url_path == "/neosmartblinds_static"


async def test_the_url_changes_when_the_card_file_changes(
    hass: HomeAssistant, tmp_path, monkeypatch
) -> None:
    www = tmp_path / "www"
    www.mkdir()
    (www / card.CARD_FILENAME).write_text("one")
    first = card._version_tag(www)
    (www / card.CARD_FILENAME).write_text("two")

    assert card._version_tag(www) != first


async def test_the_version_tag_copes_with_missing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(card, "__file__", str(tmp_path / "card.py"))  # no manifest there

    assert card._version_tag(tmp_path) == "0"  # and no card file either


async def test_serving_an_already_registered_path_is_fine(
    hass: HomeAssistant, http
) -> None:
    http.async_register_static_paths.side_effect = RuntimeError("already registered")

    assert await async_serve_card(hass)


async def test_a_missing_card_folder_means_no_card(
    hass: HomeAssistant, http, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(card, "__file__", str(tmp_path / "card.py"))

    assert await async_serve_card(hass) is None
    http.async_register_static_paths.assert_not_awaited()


# --- registering the resource --------------------------------------------------------


async def test_storage_mode_adds_the_resource(hass: HomeAssistant, http, extra_url) -> None:
    resources = FakeResources(
        [{"id": "x", "url": "/other.js", "type": "module"}], loaded=False
    )
    use_lovelace(hass, resources)

    await async_register_card(hass)
    await async_register_card(hass)  # once per run

    resources.async_load.assert_awaited_once()  # an unloaded collection is loaded first
    resources.async_create_item.assert_awaited_once()
    created = resources.async_create_item.await_args.args[0]
    assert created["res_type"] == "module"
    assert created["url"].startswith(CARD_URL)
    extra_url.add.assert_not_called()


async def test_a_stale_resource_is_pointed_at_the_new_version(
    hass: HomeAssistant, http, extra_url
) -> None:
    resources = FakeResources([{"id": "old", "url": f"{CARD_URL}?v=0.1"}])
    use_lovelace(hass, resources)

    await async_register_card(hass)

    resources.async_update_item.assert_awaited_once()
    assert resources.async_update_item.await_args.args[0] == "old"
    resources.async_create_item.assert_not_awaited()


async def test_duplicate_resources_are_removed(hass: HomeAssistant, http, extra_url) -> None:
    url = await async_serve_card(hass)
    resources = FakeResources(
        [{"id": "a", "url": url}, {"id": "b", "url": f"{CARD_URL}?v=old"}]
    )
    use_lovelace(hass, resources)

    await async_register_card(hass)

    resources.async_update_item.assert_not_awaited()  # the first one is current
    resources.async_delete_item.assert_awaited_once_with("b")


async def test_yaml_mode_loads_the_card_on_every_page(
    hass: HomeAssistant, http, extra_url
) -> None:
    use_lovelace(hass, FakeResources(), mode="yaml")

    await async_register_card(hass)

    extra_url.add.assert_called_once()
    assert extra_url.add.call_args.args[1].startswith(CARD_URL)


async def test_without_lovelace_the_card_loads_on_every_page(
    hass: HomeAssistant, http, extra_url
) -> None:
    hass.data.pop(LOVELACE_DATA, None)

    await async_register_card(hass)

    extra_url.add.assert_called_once()


async def test_a_resource_that_cannot_be_written_falls_back(
    hass: HomeAssistant, http, extra_url
) -> None:
    resources = FakeResources()
    resources.async_create_item.side_effect = RuntimeError("read only")
    use_lovelace(hass, resources)

    await async_register_card(hass)

    extra_url.add.assert_called_once()


async def test_no_card_file_means_nothing_to_register(
    hass: HomeAssistant, http, extra_url, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(card, "__file__", str(tmp_path / "card.py"))

    await async_register_card(hass)

    extra_url.add.assert_not_called()


async def test_a_failing_extra_url_is_survived(hass: HomeAssistant, http, extra_url) -> None:
    extra_url.add.side_effect = RuntimeError("frontend not ready")
    hass.data.pop(LOVELACE_DATA, None)

    await async_register_card(hass)  # must not raise

    assert "extra_url" not in hass.data[card._STATE_KEY]


# --- unregistering -------------------------------------------------------------------


async def test_unregistering_deletes_only_our_resource(
    hass: HomeAssistant, http, extra_url
) -> None:
    resources = FakeResources(
        [{"id": "ours", "url": f"{CARD_URL}?v=1"}, {"id": "theirs", "url": "/other.js"}]
    )
    use_lovelace(hass, resources)

    await async_unregister_card(hass)

    resources.async_delete_item.assert_awaited_once_with("ours")


async def test_unregistering_drops_the_every_page_fallback(
    hass: HomeAssistant, http, extra_url
) -> None:
    hass.data.pop(LOVELACE_DATA, None)
    await async_register_card(hass)

    await async_unregister_card(hass)

    extra_url.remove.assert_called_once_with(hass, extra_url.add.call_args.args[1])
    await async_register_card(hass)  # and a later account can register it again
    assert extra_url.add.call_count == 2


async def test_unregistering_survives_errors(hass: HomeAssistant, http, extra_url) -> None:
    hass.data[card._STATE_KEY] = {"lock": AsyncMock(), "extra_url": "/x.js"}
    extra_url.remove.side_effect = RuntimeError("gone already")
    resources = FakeResources([{"id": "ours", "url": CARD_URL}])
    resources.async_delete_item.side_effect = RuntimeError("read only")
    use_lovelace(hass, resources)

    await async_unregister_card(hass)  # must not raise


async def test_unregistering_without_lovelace_does_nothing(
    hass: HomeAssistant, http, extra_url
) -> None:
    hass.data.pop(LOVELACE_DATA, None)

    await async_unregister_card(hass)

    extra_url.remove.assert_not_called()
