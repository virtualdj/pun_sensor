
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, VOLUME_LITERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
import logging

from . import PUNDataHub
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.debug("Sensors async setup")
    coordinator = hass.data[DOMAIN]["coordinator"]
    #devices = await coordinator.hub.list_devices()

    #entities = []

    #for device in devices:
    #    entities.append(PUNSensorEntity(coordinator, device))   

    entities = []
    entities.append(PUNSensorEntity(coordinator, 'F1'))
    entities.append(PUNSensorEntity(coordinator, 'F2'))
    entities.append(PUNSensorEntity(coordinator, 'F3'))
    async_add_entities(entities, update_before_add=True)


class PUNSensorEntity(CoordinatorEntity, SensorEntity):
    hub: PUNDataHub
    name: str

    def __init__(self, coordinator: DataUpdateCoordinator, name: str) -> None:
        super().__init__(coordinator)
        _LOGGER.debug("PUNSensor created (" + name + ")")
        self.hub = coordinator.hub
        self._state = 0
        self._attr_name = "Real PUN " + name
        self._attr_native_unit_of_measurement = "€/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        return self.hub.nane
