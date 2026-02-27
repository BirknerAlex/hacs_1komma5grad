from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CURRENCY_ICON, DOMAIN
from .coordinator import Coordinator

class ElectricityPriceSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Energy Price Sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)

        self._system_id = system_id
        self._prices = {}
        self._price_summary = {}
        self._unit = '€/kWh' # Default unit

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return CURRENCY_ICON

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electricity Price {self._system_id}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}_electricity_price_{self._system_id}"

    @property
    def native_value(self) -> None | float:
        """Return the state of the entity."""

        current_time = (
            dt_util.now()
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(ZoneInfo("UTC"))
            .strftime("%Y-%m-%dT%H:%MZ")
        )

        if current_time in self._prices:
            current_price_data = self._prices.get(current_time)
            if current_price_data and "marketPriceWithGridCostAndVat" in current_price_data:
                return round(float(current_price_data["marketPriceWithGridCostAndVat"]), 4)

        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self) -> dict:
        """Return forecast and summary price attributes."""
        attrs = {}

        if not self._prices:
            return attrs

        now_utc = (
            dt_util.now()
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(ZoneInfo("UTC"))
        )

        # Build forecast list: future hours only, sorted chronologically
        forecast = []
        for timestamp_str, price_data in sorted(self._prices.items()):
            try:
                ts = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%MZ").replace(
                    tzinfo=ZoneInfo("UTC")
                )
            except (ValueError, TypeError):
                continue

            if ts <= now_utc:
                continue

            price_value = price_data.get("marketPriceWithGridCostAndVat")
            if price_value is not None:
                forecast.append({
                    "datetime": ts.isoformat(),
                    "price": round(float(price_value), 4),
                })

        attrs["forecast"] = forecast

        # Summary statistics from the API response
        try:
            summary = self._price_summary["energyMarketWithGridCostsAndVat"]
            attrs["price_today_min"] = round(float(summary["lowestPrice"]["price"]["amount"]), 4)
            attrs["price_today_max"] = round(float(summary["highestPrice"]["price"]["amount"]), 4)
            attrs["price_today_avg"] = round(float(summary["averagePrice"]["price"]["amount"]), 4)
        except (KeyError, TypeError, ValueError):
            pass

        # Cheapest upcoming hour
        if forecast:
            cheapest = min(forecast, key=lambda x: x["price"])
            attrs["cheapest_upcoming_hour"] = cheapest["datetime"]
            attrs["cheapest_upcoming_price"] = cheapest["price"]

        attrs["forecast_hours_available"] = len(forecast)

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        prices = self.coordinator.get_prices_by_id(self._system_id)

        if "timeseries" not in prices:
            self.coordinator.logger.error("Timeseries data not found in coordinator data")
            return

        self._prices = prices["timeseries"]
        self._price_summary = prices

        # Determine currency from response metadata
        try:
            currency = prices["timeseriesMetadata"]["units"]["price"]["currency"]
            per_unit = prices["timeseriesMetadata"]["units"]["price"]["perUnit"]
            self._unit = f"{currency}/{per_unit}"
        except (KeyError, TypeError):
            self._unit = "€/kWh"

        self.async_write_ha_state()
