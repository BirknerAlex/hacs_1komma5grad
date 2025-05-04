from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CURRENCY_ICON, DOMAIN, TIMEZONE
from .coordinator import Coordinator

class ElectricityPriceSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Energy Price Sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)

        self._system_id = system_id
        self._prices = {}
        self._vat = 0
        self._grid_costs = 0
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

        tz = ZoneInfo(TIMEZONE)
        current_time = (
            dt_util.now()
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(tz)
            .strftime("%Y-%m-%dT%H:%MZ")
        )

        if current_time in self._prices:
            current_price_data = self._prices.get(current_time)
            current_price = 0
            if current_price_data and "price" in current_price_data:
                current_price = float(current_price_data["price"])

            total_net = float(current_price + self._grid_costs)

            return round(total_net / 100.0 * self._vat, 4)

        return None

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        prices = self.coordinator.get_prices_by_id(self._system_id)

        if "vat" not in prices:
            self.coordinator.logger.error("VAT not found in coordinator data")
            return

        if ("gridCostsComponents" not in prices or
                not isinstance(prices["gridCostsComponents"], dict) or
                "purchasingCost" not in prices["gridCostsComponents"] or
                not isinstance(prices["gridCostsComponents"]["purchasingCost"], dict) or
                "energyTax" not in prices["gridCostsComponents"] or
                not isinstance(prices["gridCostsComponents"]["energyTax"], dict) or
                "value" not in prices["gridCostsComponents"]["purchasingCost"] or
                "value" not in prices["gridCostsComponents"]["energyTax"]):
            self.coordinator.logger.error("Grid costs components not found in coordinator data")
            return

        if "energyMarket" not in prices or "data" not in prices["energyMarket"]:
            self.coordinator.logger.error("Energy market data not found in coordinator data")
            return

        self._vat = float(prices["vat"] + 1)

        # Grid costs are the sum of the purchasing cost and the energy tax in ct/kWh
        try:
            self._grid_costs = float(prices["gridCostsComponents"]["purchasingCost"]["value"] + prices["gridCostsComponents"]["energyTax"]["value"])
        except (KeyError, TypeError):
            self.coordinator.logger.error("Grid costs components not found in coordinator data")
            self._grid_costs = 0

        # prices is a dict with the time as key and the price as value
        self._prices = prices["energyMarket"]["data"]

        # price unit e.g. "€/kWh"
        self._unit = "€/kWh" # TODO: fetch currency from API somehow

        self.async_write_ha_state()
