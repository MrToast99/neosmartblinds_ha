# Neo Smart Blinds (Cloud) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

This is a custom integration for Home Assistant to control [Neo Smart Blinds](https://neosmartblinds.com/) via their cloud API.

This integration provides:
* **Cover Entities:** For each blind, allowing you to open, close, stop, and trigger favorite positions.
* **Schedule Switches:** Creates switch entities for each schedule in the Neo app, allowing you to enable or disable them from Home Assistant.
* **Custom Services:** `neosmartblinds_ha.favorite_1` and `neosmartblinds_ha.favorite_2` for use in automations.

## Installation

### HACS (Recommended)

1.  This integration is not yet in the default HACS repository.
2.  You can add it as a **custom repository**:
    * Go to HACS > Integrations > (three dots menu) > Custom repositories.
    * Paste the URL to this GitHub repository in the "Repository" field.
    * Select "Integration" as the category.
    * Click "Add".
3.  The integration will now appear in HACS. Click "Install" and follow the prompts.

### Manual Installation

1.  Using the tool of your choice, copy the `neosmartblinds_ha` directory (from the `custom_components` folder in this repo) into your Home Assistant `custom_components` folder.
2.  Restart Home Assistant.

## Configuration

Configuration is done through the Home Assistant UI:

1.  Go to **Settings > Devices & Services**.
2.  Click the **+ Add Integration** button.
3.  Search for "Neo Smart Blinds (Cloud)" and select it.
4.  You will be prompted for your Neo Smart Blinds app **Username (Email)** and **Password**.
5.  The integration will log in, discover your devices, and add them to Home Assistant.

## How It Works

This integration works by polling the official Neo Smart Blinds cloud API.

* **Automatic Entity Setup:** After you log in, the integration automatically queries the cloud for your account details. It then creates Home Assistant cover and switch entities for all the blinds and schedules registered to your account.
* **Cloud Requirement:** This integration **only** works with blinds that are already set up and connected in the Neo Smart Blinds app. It relies entirely on the cloud connection and does not support local-only control.

## Features

### Cover Controls

Each blind will appear as a `cover` entity.

* **Open/Close/Stop:** Standard controls.
* **Favorite 1 (Tilt Open):** The "Tilt Open" button (upward-pointing tilt arrow) is mapped to the `favorite_1` service. This will send the `gp` (Go to Position) command for most motors or `i1` for "no" and "rx" motors.
* **Favorite 2 (Tilt Close):** The "Tilt Close" button (downward-pointing tilt arrow) is mapped to the `favorite_2` service. This will only appear for motors that support a second favorite position ("no" and "rx").

### Schedule Switches

Each schedule you have configured in the Neo Smart Blinds app will appear as a `switch` entity.

* Turning the switch **on** enables the schedule in the cloud.
* Turning the switch **off** disables the schedule in the cloud.

The switches will have icons corresponding to their action (e.g., `mdi:numeric-1-circle` for a "Favorite 1" schedule).

### Services

The integration provides two services for more direct control in automations and scripts.

#### `neosmartblinds_ha.favorite_1`
Moves the target blind to its Favorite 1 position.
* **Icon:** `mdi:numeric-1-circle`

#### `neosmartblinds_ha.favorite_2`
Moves the target blind to its Favorite 2 position (only supported on "no" and "rx" motors).
* **Icon:** `mdi:numeric-2-circle`

**Example Service Call:**
```yaml
- service: neosmartblinds_ha.favorite_1
  target:
    entity_id: cover.my_blind_name
```

## Credits

* Original code by [@MrToast99](https://github.com/MrToast99).
