
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from typing import Any, Dict

from . import PUNDataUpdateCoordinator
from .const import (
    DOMAIN,
    PUN_FASCIA_MONO,
    PUN_FASCIA_F1,
    PUN_FASCIA_F2,
    PUN_FASCIA_F3,
    COORD_EVENT,
    EVENT_UPDATE_FASCIA,
    EVENT_UPDATE_PUN,
)
ATTR_ROUNDED_DECIMALS = "rounded_decimals"

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None) -> None:
    """Inizializza e crea i sensori"""

    # Restituisce il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Aggiunge i sensori (legati al coordinator)
    entities = []
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_MONO))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F1))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F2))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F3))
    entities.append(FasciaPUNSensorEntity(coordinator))
    entities.append(PrezzoFasciaPUNSensorEntity(coordinator))
    async_add_entities(entities, update_before_add=True)
    

def fmt_float(num: float):
    """Formatta la media come numero decimale con 6 decimali (ma arrotondato al quinto)"""
    return format(round(num, 5), '.6f')

class PUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore PUN relativo al prezzo medio mensile per fasce"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator, tipo: int) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator
        self.tipo = tipo

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._available = False
        self._native_value = 0

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        self.async_write_ha_state()
        #_LOGGER.debug('SENSOR HANDLE COORDINATOR: PUNSensorEntity (F%s)', self.tipo)

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico"""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        return self.coordinator.orari[self.tipo] > 0

    @property
    def native_value(self) -> float:
        """Valore corrente del sensore"""
        return self.coordinator.pun[self.tipo]

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura"""
        return "€/kWh"

    @property
    def state(self) -> str:
        return fmt_float(self.native_value)

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:chart-line"

    @property
    def entity_id(self) -> str:
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
    def name(self) -> str:
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

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Restituisce gli attributi di stato"""
        state_attr = {
            ATTR_ROUNDED_DECIMALS: round(self.native_value, 3)
        }
        return state_attr

class FasciaPUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore che rappresenta la fascia PUN corrente"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator
        self.coordinator = coordinator

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        #if (self.coordinator.data and self.coordinator.data[COORD_EVENT] == EVENT_UPDATE_FASCIA):
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico"""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        return self.coordinator.fascia_corrente is not None
    
    @property
    def state(self) -> str:
        """Restituisce la fascia corrente come stato"""
        if (self.coordinator.fascia_corrente == 3):
            return "F3"
        elif (self.coordinator.fascia_corrente == 2):
            return "F2"
        elif (self.coordinator.fascia_corrente == 1):
            return "F1"
        else:
            return None

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:timeline-clock-outline"

    @property
    def entity_id(self) -> str:
        """Restituisce l'entity id del sensore"""
        return DOMAIN + ".fascia_corrente"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Fascia corrente"

class PrezzoFasciaPUNSensorEntity(FasciaPUNSensorEntity):
    """Sensore che rappresenta il prezzo PUN della fascia corrente"""

    @property
    def state_class(self) -> str:
        return SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        if super().available:
            if (self.coordinator.fascia_corrente == 3):
                return self.coordinator.orari[PUN_FASCIA_F3] > 0
            elif (self.coordinator.fascia_corrente == 2):
                return self.coordinator.orari[PUN_FASCIA_F2] > 0
            elif (self.coordinator.fascia_corrente == 1):
                return self.coordinator.orari[PUN_FASCIA_F1] > 0
        return False

    @property
    def native_value(self) -> float:
        """Restituisce il prezzo della fascia corrente"""
        if (self.coordinator.fascia_corrente == 3):
            return self.coordinator.pun[PUN_FASCIA_F3]
        elif (self.coordinator.fascia_corrente == 2):
            return self.coordinator.pun[PUN_FASCIA_F2]
        elif (self.coordinator.fascia_corrente == 1):
            return self.coordinator.pun[PUN_FASCIA_F1]
        else:
            return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura"""
        return "€/kWh"

    @property
    def state(self) -> str:
        return fmt_float(self.native_value)

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:currency-eur"

    @property
    def entity_id(self) -> str:
        """Restituisce l'entity id del sensore"""
        return DOMAIN + ".prezzo_fascia_corrente"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Prezzo fascia corrente"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Restituisce gli attributi di stato"""
        state_attr = {
            ATTR_ROUNDED_DECIMALS: round(self.native_value, 3)
        }
        return state_attr