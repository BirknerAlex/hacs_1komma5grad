<img src="https://raw.githubusercontent.com/BirknerAlex/hacs_1komma5grad/main/images/icon.png" alt="1KOMMA5GRAD Logo" title="1KOMMA5GRAD Home Assistant Integration" align="right" height="60" />

# 1KOMMA5GRAD Home Assistant Integration

This is a HACS integration for [Home Assistant](https://www.home-assistant.io/) to integrate 1KOMMA5GRAD 
into your Home Assistant instance.

This integration is not related to 1KOMMA5GRAD and not officially supported by them.

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BirknerAlex&repository=hacs_1komma5grad&category=integration)

## Limited availability

This integration is for the latest 1KOMMA5GRAD Heartbeat API.

> Warning: The new API is not available for all regions yet. The new API is required to use this integration with Home Assistant.

To check if you are using the latest generation of the Heartbeat API, please try login on https://app.1komma5grad.com/.

Currently supported regions for the new API are (as of December 2025):

- Austria
- Germany
- Netherlands
- Sweden
- Switzerland

You can check this also by going to https://gaia-charge.github.io/app-not-available/ and enter `6455889609` as App ID.
This checks if the latest iOS App is available in your region, which also uses the new API.

If you are still using https://my.1komma5.io/ for login (or the old App), you are still using the old API and please use this
https://github.com/derlangemarkus/1komma5grad_ha to integrate 1KOMMA5GRAD into Home Assistant instead.

## Warning 

This integration is fully community driven and not officially supported by 1KOMMA5GRAD. Use at your own risk.
We are not responsible for any damage or issues caused by using this integration.

This integration is not affiliated with or endorsed by 1KOMMA5GRAD.

This integration is regularly tested against the following Heartbeat components:

- Chint DTSU666 (Power Meter) 
- Mennekes Amtron Compact 2.0S (EV Charger)

Other components like heat pumps are not tested due to lack of hardware availability.

## Contribute

If you want to contribute to this project, please have a look at the [CONTRIBUTE.md](CONTRIBUTE.md) file.
