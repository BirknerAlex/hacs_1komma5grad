"""Helpers for building DeviceInfo from coordinator device data."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DeviceType
from .coordinator import Coordinator, DeviceData

# Maps our DeviceType enum to the API's asset type strings
_DEVICE_TYPE_TO_ASSET: dict[DeviceType, tuple[str, str]] = {
    DeviceType.HYBRID: ("HYBRID", "Inverter / Battery"),
    DeviceType.EV_CHARGER: ("EV_CHARGER", "EV Charger"),
    DeviceType.HEAT_PUMP: ("HEAT_PUMP", "Heat Pump"),
}


def _gateway_device_info(device_data: DeviceData) -> DeviceInfo | None:
    """Build DeviceInfo for the Heartbeat gateway."""
    if device_data is None or device_data.gateway is None:
        return None
    gw = device_data.gateway
    return DeviceInfo(
        identifiers={(DOMAIN, gw.serial_number)},
        name=f"Heartbeat {gw.system_name}" if gw.system_name else "Heartbeat",
        manufacturer="1KOMMA5\u00b0",
        model="Heartbeat",
        serial_number=gw.serial_number,
    )


def _asset_device_info(
    device_data: DeviceData, asset_type: str, fallback_name: str
) -> DeviceInfo | None:
    """Build DeviceInfo for a specific asset type (HYBRID, EV_CHARGER, HEAT_PUMP, etc.)."""
    if device_data is None or device_data.assets_by_type is None:
        return None
    asset = device_data.assets_by_type.get(asset_type)
    if asset is None:
        return None
    identifier = asset.serial_number or asset.asset_id
    if not identifier:
        return None
    via = None
    if device_data.gateway:
        via = (DOMAIN, device_data.gateway.serial_number)
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=asset.model or asset.name or fallback_name,
        manufacturer=asset.manufacturer,
        model=asset.model,
        serial_number=asset.serial_number,
        via_device=via,
    )


def get_device_info(
    coordinator: Coordinator, system_id: str, device_type: DeviceType | None
) -> DeviceInfo | None:
    """Return DeviceInfo for the given device_type, or None if unavailable."""
    if device_type is None:
        return None
    device_data = coordinator.get_device_data_by_id(system_id)
    if device_data is None:
        return None
    if device_type == DeviceType.GATEWAY:
        return _gateway_device_info(device_data)
    mapping = _DEVICE_TYPE_TO_ASSET.get(device_type)
    if mapping:
        return _asset_device_info(device_data, mapping[0], mapping[1])
    return None
