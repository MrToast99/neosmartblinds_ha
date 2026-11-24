# Neo Smart Blinds (Cloud) Integration for Home Assistant

<!-- ha-marketplace:exclude-start -->
[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=MrToast99&repository=NeoSmartBlinds_HA&category=integration)
<!-- ha-marketplace:exclude-end -->

Control your [Neo Smart Blinds](https://neosmartblinds.com/) from Home Assistant through the Neo cloud, the same service the Neo Smart Blinds app uses.

* **Covers:** every blind and every room, with open, close, stop and (where the motor supports it) a position.
* **Favorite buttons:** "Favorite 1" and "Favorite 2" for each blind and each room.
* **Schedule switches:** turn the schedules from the Neo app on or off.
* **Dashboard card and sidebar page:** room tiles laid out like the Neo app (see [Dashboard card](#dashboard-card)).

> **Cloud only.** This works only with blinds already set up in the Neo Smart Blinds app, and it needs an internet connection. There is no local control.

## Installation

Requires Home Assistant 2026.11 or newer.

### Marketplace (recommended)

This integration is not in the default catalog yet, so add it from its link:

1.  Click the badge above, or in Home Assistant open the **Marketplace** and choose **Add from link**. Paste this repository's URL and pick the category **Integration**.
2.  Install **Neo Smart Blinds (Cloud)**.
3.  Add the integration as described under [Configuration](#configuration). A first install needs no restart.

### Manual installation

1.  Copy the `neosmartblinds` folder from this repository's `custom_components` folder into your Home Assistant `custom_components` folder.
2.  Restart Home Assistant.

## Configuration

1.  Go to **Settings > Devices & Services** and click **Add Integration**.
2.  Search for **Neo Smart Blinds (Cloud)**.
3.  Enter the **Username (Email)** and **Password** you use in the Neo Smart Blinds app.
4.  Choose whether to **Show Neo Blinds in the sidebar** (on by default).

The integration signs in, finds your rooms, controllers, blinds and schedules, and creates the devices and entities for them. Your login is stored in Home Assistant's config entry so the integration can sign in again, and it is only sent to the Neo cloud.

### Options

Open the integration and choose **Configure** to change:

* **Show Neo Blinds in the sidebar:** adds or removes the sidebar page.
* **Debug Logging Level:** how much of the data sent to the Neo cloud is written to the debug log. The default is redacted. Choose full logging only while troubleshooting, and don't post those logs publicly, because they are not redacted.

Changing an option reloads the integration.

## What you get

| Device | Entities |
| --- | --- |
| **Account** | The top-level device for your login. |
| **Controller** (one per Neo controller, named after its room) | A cover and two favorite buttons for each room ("Room: Dining", "Room: Dining Favorite 1"), plus a switch for each schedule. |
| **Blind** (one per blind, under its controller) | A cover, plus "Favorite 1" and "Favorite 2" buttons. |

* **Blind covers** support open, close and stop. A position slider is added for motors that report percent support.
* **Room covers** open, close or stop every blind in the room at once. They have no position of their own; use the blinds or the card's "set position" slider for that.
* **Favorite buttons** are created for every blind and room. They only do something on motors that have a favorite position set.
* **Schedule switches** are named from the room, action and time, for example "Master Favorite 1 at 7:00". Turning one on or off enables or disables that schedule in the cloud.

The `neosmartblinds.favorite_1` and `neosmartblinds.favorite_2` services also still work on cover entities, but the buttons above are easier to use in dashboards and automations (`button.press`).

### How state works

The Neo cloud doesn't report where a blind is, so Home Assistant only knows what it last told the blind to do. A blind moved with the remote or the Neo app won't update in Home Assistant, and the covers are marked as having an assumed state.

Rooms, blinds and schedules are read when the integration loads. If you add a blind or change a schedule in the Neo app, reload the integration (**Settings > Devices & Services > Neo Smart Blinds > ⋮ > Reload**) to pick it up.

## Dashboard card

The integration serves its own card and adds it to your dashboard resources, so there is nothing to copy or install. Add it from the card picker (**Neo Smart Blinds**) or in YAML:

```yaml
type: custom:neosmartblinds-card
title: Blinds              # optional
room: Master               # optional; leave out to list every room
show_all: true             # optional, an "All rooms" tile above the rooms
show_blinds: true          # optional, expandable list of each blind in a room
show_schedules: true       # optional, schedule switches inside a room
start_expanded: false      # optional, open every room's details at first
```

Each room tile has open, stop, close, Favorite 1, Favorite 2 and a "set position" slider for the whole room. Expand a room to control each blind on its own and to switch its schedules on or off.

If your dashboards are in YAML mode, resources can't be written for you, so the card is loaded on every page instead.

### Sidebar page

The same card is also a page of its own in Home Assistant's sidebar, with no dashboard needed. It is on by default for new accounts. Accounts added before this option existed keep it off until you turn on **Show Neo Blinds in the sidebar** under **Configure**.

## Troubleshooting

* **Controls do nothing, or you see an error in the log:** check that the same action works in the Neo Smart Blinds app, then reload the integration.
* **The login fails:** use the email and password from the Neo Smart Blinds app. If you changed your password there, remove the integration and add it again.
* **The card says the integration isn't loaded:** the integration failed to start. Check **Settings > System > Logs** for `neosmartblinds`.
* **A bug or a question:** [open an issue](https://github.com/MrToast99/NeoSmartBlinds_HA/issues) and include the Home Assistant version, the integration version and the relevant log lines.

## Credits

* Original code by [@MrToast99](https://github.com/MrToast99).
* Released under the [MIT License](LICENSE).
* This is an unofficial, community-made integration. It is not affiliated with, endorsed by or supported by Neo Smart Blinds. The Neo Smart Blinds name and logo are trademarks of their owner and are used here only to identify the product this integration works with.
