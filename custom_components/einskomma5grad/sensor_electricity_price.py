from zoneinfo import ZoneInfo

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CURRENCY_ICON, DOMAIN, TIMEZONE
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)

class ElectricityPriceSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Energy Price Sensor."""

    def __init__(self, coordinator: Coordinator, system_id: str) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)

        self._system_id = system_id
        self._prices = {}
        self._vat = 0
        self._grid_costs = 0
        self._unit = 'ct/kWh' # Default unit

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return CURRENCY_ICON

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electricity Price {self._system_id}"

    @property
    def unit_of_measurement(self):
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
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.

        tz = ZoneInfo(TIMEZONE)
        current_time = (
            dt_util.now()
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(tz)
            .strftime("%Y-%m-%dT%H:%MZ")
        )

        # self._prices is an dict where the time is the key and the price is in another dict with "price" as key
        if current_time in self._prices:
            # Current price contains the amount of cents per kWh
            current_price = float(self._prices[current_time]["price"])
            total_net = float(current_price + self._grid_costs)

            logging.debug("Current price: %s", current_price)
            logging.debug("Grid costs: %s", self._grid_costs)
            logging.debug("Total net: %s", total_net)
            logging.debug("VAT: %s", self._vat)

            # round price to 1 decimal place and convert from ct/kWh to €/kWh and add VAT
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

        self._vat = float(prices["vat"] + 1)

        # Grid costs are the sum of the purchasing cost and the energy tax in ct/kWh
        self._grid_costs = float(prices["gridCostsComponents"]["purchasingCost"]["value"] + prices["gridCostsComponents"]["energyTax"]["value"])

        # prices is a dict with the time as key and the price as value
        self._prices = prices["energyMarket"]["data"]

        # price unit e.g. "€/kWh"
        self._unit = "€/kWh" # TODO: fetch currency from API somehow

        self.async_write_ha_state()
