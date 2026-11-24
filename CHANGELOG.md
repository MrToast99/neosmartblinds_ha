# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions match the release tags.

## [1.2.2] - pending

Failed commands now report an error, plus groundwork from the Home Assistant quality scale.

### Changed
- **Failed commands are reported.** When the Neo cloud doesn't accept a command or a schedule change, Home Assistant now shows an error and the entity keeps its previous state. Before, the failure was only written to the log and the entity looked as if it had worked. A room command tries every blind and says how many didn't respond.
- The two `favorite` actions are registered once when Home Assistant starts, instead of once per account.
- Commands are sent to the Neo cloud one entity at a time (`PARALLEL_UPDATES = 1`), so a burst of commands doesn't flood it.
- Account data is kept in the config entry's `runtime_data` instead of `hass.data`.
- Entities share a base class (`entity.py`) and are marked as never polled.

### Added
- README sections for the actions and for removing the integration.

## [1.2.1] - 2026-11-23

Reauthentication after a password change, and sample images in the README.

### Added
- **Reauthentication**: if the Neo Smart Blinds password changes, Home Assistant now asks for the new one (a "Reconfigure/Re-authenticate" prompt on the integration) instead of making you remove and add the integration again. It starts at setup and also when a running integration finds its login rejected. The new password must belong to the same Neo account.
- Sample dashboard card and sidebar page images in the README.

### Changed
- When an access token can't be refreshed, the integration now signs in again with the saved password instead of failing every command until the next restart.
- A Neo cloud outage (server errors, no connection) while loading is no longer treated as a wrong password, and the integration retries on its own instead of staying failed.

## [1.2.0] - 2026-11-23

Marketplace support, a dashboard card and sidebar page, and fixes for room controls and the options dialog. Requires Home Assistant 2026.11 or newer.

### Added
- **Dashboard card** (`custom:neosmartblinds-card`): one tile per room with open, stop, close, Favorite 1, Favorite 2 and a "set position" slider, an "All rooms" tile, and an expandable list of each blind and each schedule. It has a visual editor, and the integration serves it and registers the Lovelace resource itself.
- **Sidebar page**: the same card as a page of its own. Turn it on or off with **Show Neo Blinds in the sidebar** in the setup form or the integration's **Configure** dialog. It is on by default for new accounts; existing accounts keep it off until enabled.
- Support for the Home Assistant Marketplace: `categories`, `integration_type` and the dependencies the card needs in `manifest.json`, a minimum Home Assistant version in `hacs.json`, brand icons (`brand/icon.png` and `icon@2x.png`), a complete `translations/en.json`, and a `validate.yaml` workflow (HACS action, hassfest and unit tests).
- Unit tests for the data the card is built from.
- An MIT `LICENSE` file, which the HACS validation requires.

### Changed
- Device links use `via_device_id` instead of the deprecated `via_device`, which stops working in Home Assistant 2027.8.0.
- Looking up the controller device uses `async_get_device_by_identifier` with the config entry, because `async_get_device` is deprecated.
- The release workflow now fails if the release tag doesn't match the manifest version, and attaches `neosmartblinds.zip` for manual installs.
- README rewritten: Marketplace install steps, options, entities, how state works, the card and sidebar page, and troubleshooting.

### Fixed
- Room covers failed on open, close and stop with `'NeoSmartRoomCover' object has no attribute '_motor_code'` ([#3](https://github.com/MrToast99/NeoSmartBlinds_HA/issues/3)). The room favorite buttons and the individual favorite buttons had the same bug. Each blind's own motor type is now used.
- The integration's **Configure** dialog failed with "500 Internal Server Error".
- The release workflow changed into a folder that doesn't exist, so releases failed.
- `hacs.json` listed the wrong domain (`neosmartblinds_ha`).
- Hassfest rejected `icon` in `services.yaml`. The service icons now live in `icons.json`.

### Removed
- The `platforms` key in `manifest.json`, which is not a valid manifest key.
- `strings.json`. Custom integrations use `translations/en.json`, which now holds the same text.

## [1.1.3] - 2026-09-04

### Changed
- Updated for the `device_registry.async_get_device` deprecation.

## [1.1.2] - 2026-05-27

### Added
- PKCE authentication flow for Neo Smart Blinds login.

## [1.1.1] - 2026-03-01

### Changed
- Code cleanup.

## [1.1.0] - 2025-12-28

### Changed
- Further room control refinement.

## [1.0.9] - 2025-12-28

### Added
- Room control.

### Changed
- Entity naming updates.
- Code cleanup.

## [1.0.8] - 2025-12-28

### Changed
- Entity naming updates.

## [1.0.7] - 2025-12-28

### Changed
- Manifest update.

## [1.0.6] - 2025-12-28

### Changed
- Restructured the integration's files.

## [1.0.5] - 2025-11-17

### Added
- New debug logging toggles.

## [1.0.4] - 2025-11-15

### Fixed
- Token refresh revision.

## [1.0.3] - 2025-11-14

### Fixed
- A race condition and a file name.

## [1.0.2] - 2025-11-13

### Added
- Favorite controls.
- Grouping of entities into devices.

## [1.0.1] - 2025-11-13

### Fixed
- Corrected the motor code query.

## [1.0.0] - 2025-11-13

### Added
- Initial release.

<!--
Versions before 1.2.0 are summarised from their GitHub release titles and notes, which are brief,
so those entries are less detailed than the current ones.
-->

[1.2.2]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.9...v1.1.0
[1.0.9]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/MrToast99/NeoSmartBlinds_HA/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/MrToast99/NeoSmartBlinds_HA/releases/tag/v1.0.0
