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

## Entities

The integration creates the following entities per system:

### Sensors

| Entity | Description |
|--------|-------------|
| Electricity Price | Current electricity price (incl. grid costs and VAT). Includes forecast attributes (see below). |
| Grid Feed In Power | Power currently imported from the grid (W) |
| Grid Feed Out Power | Power currently exported to the grid (W) |
| Grid Feed Power | Net grid power flow (W) |
| Consumption Power | Total household consumption (W) |
| Solar Production Power | Current solar panel output (W) |
| EV Chargers Aggregated Power | Combined power of all EV chargers (W) |
| Heat Pumps Aggregated Power | Combined power of all heat pumps (W) |
| Battery State of Charge | Battery charge level (%) |
| Battery In Power | Power flowing into the battery (W) |
| Battery Out Power | Power flowing out of the battery (W) |

Energy sensors (kWh) are also created for grid in/out, solar production, EV chargers, heat pumps, and battery in/out to enable the HA Energy Dashboard.

### Switches

| Entity | Description |
|--------|-------------|
| Heartbeat Automatic Mode | Toggle the Energy Management System (EMS) automatic mode on/off |

### Select

| Entity | Description |
|--------|-------------|
| EV Charging Mode | Select charging mode per EV (e.g. SMART_CHARGE, SOLAR_CHARGE, QUICK_CHARGE) |

### Number

| Entity | Description |
|--------|-------------|
| EV Current State of Charge | Current EV battery charge level (0-100%). Can be set manually. |

## Electricity Price Forecast

The electricity price sensor exposes future hourly prices as extra state attributes. This allows you to build automations based on upcoming prices (e.g. run appliances during the cheapest hours).

Prices for the current day are always available. Next-day prices are typically published around 14:00 CET.

### Available attributes

| Attribute | Description |
|-----------|-------------|
| `forecast` | List of future hourly prices as `{datetime, price}` objects |
| `price_today_min` | Lowest price of the current day |
| `price_today_max` | Highest price of the current day |
| `price_today_avg` | Average price of the current day |
| `cheapest_upcoming_hour` | ISO datetime of the cheapest future hour |
| `cheapest_upcoming_price` | Price at the cheapest future hour |
| `forecast_hours_available` | Number of future hours available (indicates if next-day prices are published) |

### Template examples

You can use these in Developer Tools > Templates or in automations:

```yaml
# Current price
{{ states('sensor.electricity_price_YOUR_SYSTEM_ID') }}

# Forecast list
{{ state_attr('sensor.electricity_price_YOUR_SYSTEM_ID', 'forecast') }}

# Cheapest upcoming hour
{{ state_attr('sensor.electricity_price_YOUR_SYSTEM_ID', 'cheapest_upcoming_hour') }}

# Average price today
{{ state_attr('sensor.electricity_price_YOUR_SYSTEM_ID', 'price_today_avg') }}
```

### Automation example

Start a device when the cheapest upcoming hour begins:

```yaml
automation:
  - alias: "Run dishwasher at cheapest hour"
    trigger:
      - platform: template
        value_template: >
          {{ now().isoformat()[:13] ==
             state_attr('sensor.electricity_price_YOUR_SYSTEM_ID', 'cheapest_upcoming_hour')[:13] }}
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.dishwasher
```

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
