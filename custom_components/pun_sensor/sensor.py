
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from . import PUNDataUpdateCoordinator
from .const import DOMAIN, PUN_FASCIA_MONO, PUN_FASCIA_F1, PUN_FASCIA_F2, PUN_FASCIA_F3

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass: HomeAssistant, config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None) -> None:
    """Inizializza e crea i sensori"""
    _LOGGER.debug("Sensors async setup")

    # Restituisce il coordinator
    coordinator = hass.data[DOMAIN]["coordinator"]

    # Aggiunge i sensori (legati al coordinator)
    entities = []
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_MONO))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F1))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F2))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F3))
    async_add_entities(entities, update_before_add=True)


class PUNSensorEntity(CoordinatorEntity, SensorEntity):

    def __init__(self, coordinator: PUNDataUpdateCoordinator, tipo: int) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator
        self.tipo = tipo

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._available = False
        self._native_value = 0

    @property
    def available(self):
        """Determina se il valore è disponibile"""
        return self.coordinator.orari[self.tipo] > 0

    @property
    def native_value(self):
        """Valore corrente del sensore"""
        return self.coordinator.pun[self.tipo]

    @property
    def native_unit_of_measurement(self):
        """Unita' di misura"""
        return "€/kWh"

    @property
    def icon(self):
        """Icona da usare nel frontend"""
        return "mdi:chart-line"

    @property
    def entity_id(self):
        """Restituisce l'entity id del sensore"""
        if (self.tipo == PUN_FASCIA_F3):
            return DOMAIN + ".fascia_f3"
        elif (self.tipo == PUN_FASCIA_F2):
            return DOMAIN + ".fascia_f2"
        elif (self.tipo == PUN_FASCIA_F1):
            return DOMAIN + ".fascia_f1"
        elif (self.tipo == PUN_FASCIA_MONO):
            return DOMAIN + ".mono_orario"
        else:
            return None

    @property
    def name(self):
        """Restituisce il nome del sensore"""
        if (self.tipo == PUN_FASCIA_F3):
            return "PUN fascia F3"
        elif (self.tipo == PUN_FASCIA_F2):
            return "PUN fascia F2"
        elif (self.tipo == PUN_FASCIA_F1):
            return "PUN fascia F1"
        elif (self.tipo == PUN_FASCIA_MONO):
            return "PUN mono-orario"
        else:
            return None