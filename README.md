# Neo Smart Blinds (Cloud) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

This is a custom integration for Home Assistant to control [Neo Smart Blinds](https://neosmartblinds.com/) via their cloud API.

This integration provides:
* **Cover Entities:** For each blind, allowing you to open, close, stop, and set a specific position.
* **Button Entities:** Dedicated "Favorite 1" and "Favorite 2" buttons for motors that support them (e.g., "no" and "rx" types).
* **Schedule Switches:** Creates `switch` entities for each schedule in the Neo app, allowing you to enable or disable them from Home Assistant.
* **Logical Device Hierarchy:** Organizes entities into Account, Controller, and Blind devices for a clean UI.

## Installation

### HACS (Recommended)

1.  This integration is not yet in the default HACS repository.
2.  You can add it as a **custom repository**:
    * Go to HACS > Integrations > (three dots menu) > Custom repositories.
    * Paste the URL to this GitHub repository in the "Repository" field.
    * Select "Integration" as the category.
    * Click "Add".
3.  The integration will now appear in HACS. Click "Install" and follow the prompts.
4.  Restart Home Assistant.

### Manual Installation

1.  Using the tool of your choice, copy the `neosmartblinds_ha` directory (from the `custom_components` folder in this repo) into your Home Assistant `custom_components` folder.
2.  Restart Home Assistant.

## Configuration

Configuration is done through the Home Assistant UI:

1.  Go to **Settings > Devices & Services**.
2.  Click the **+ Add Integration** button.
3.  Search for "Neo Smart Blinds (Cloud)" and select it.
4.  You will be prompted for your Neo Smart Blinds app **Username (Email)** and **Password**.
5.  The integration will log in, discover your account, controllers, blinds, and schedules, and create all the corresponding devices and entities.

## How It Works

This integration works by polling the official Neo Smart Blinds cloud API.

* **Automatic Entity Setup:** After you log in, the integration automatically queries the cloud for your account details. It then creates a logical hierarchy of devices:
    * An **Account** device (top-level).
    * A **Controller** device for each hub, linked to the Account.
    * A **Blind** device for each blind, linked to its parent Controller.
    * Entities (`cover`, `button`, `switch`) are then attached to the correct device.
* **Cloud Requirement:** This integration **only** works with blinds that are already set up and connected in the Neo Smart Blinds app. It relies entirely on the cloud connection and does not support local-only control.

## Features

This integration creates a new "Blind" device for each of your blinds, which contains the cover and favorite buttons. Schedule switches are attached to the "Controller" device.

### Cover Controls

Each blind will appear as a `cover` entity attached to its "Blind" device. This entity provides:
* Open, Close, and Stop controls.
* A position slider (if supported by the motor).
* **Note:** The tilt buttons are no longer used. Favorite controls have been moved to dedicated `button` entities.

### Favorite Buttons

For motors that support favorite positions (like "no" and "rx" types), the integration will automatically create two new entities on the "Blind" device:
* **Favorite 1:** A `button` entity to move the blind to its first favorite position.
* **Favorite 2:** A `button` entity to move the blind to its second favorite position.

You can use these buttons in your dashboards or call the `button.press` service in automations.

### Schedule Switches

Each schedule you have configured in the Neo Smart Blinds app will appear as a `switch` entity attached to its "Controller" device.
* The switch name is automatically generated based on the room, action, and time (e.g., "Master Favorite 1 at 7:00").
* Turning the switch **on** enables the schedule in the cloud.
* Turning the switch **off** disables the schedule in the cloud.

## Credits

* Original code by [@MrToast99](https://github.com/MrToast99).
