from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
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
)
ATTR_ROUNDED_DECIMALS = "rounded_decimals"

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None) -> None:
    """Inizializza e crea i sensori"""

    # Restituisce il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Crea i sensori (legati al coordinator)
    entities = []
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_MONO))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F1))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F2))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F3))
    entities.append(FasciaPUNSensorEntity(coordinator))
    entities.append(PrezzoFasciaPUNSensorEntity(coordinator))

    # Aggiunge i sensori ma non aggiorna automaticamente via web
    # per lasciare il tempo ad Home Assistant di avviarsi
    async_add_entities(entities, update_before_add=False)
    

def fmt_float(num: float):
    """Formatta la media come numero decimale con 6 decimali"""
    return format(round(num, 6), '.6f')

class PUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore PUN relativo al prezzo medio mensile per fasce"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator, tipo: int) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator
        self.tipo = tipo

        # ID univoco sensore basato su un nome fisso
        if (self.tipo == PUN_FASCIA_F3):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f3')
        elif (self.tipo == PUN_FASCIA_F2):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f2')
        elif (self.tipo == PUN_FASCIA_F1):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f1')
        elif (self.tipo == PUN_FASCIA_MONO):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_mono_orario')
        else:
            self.entity_id = None
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._available = False
        self._native_value = 0

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        self.async_write_ha_state()

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
            ATTR_ROUNDED_DECIMALS: str(format(round(self.native_value, 3), '.3f'))
        }
        return state_attr

class FasciaPUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore che rappresenta la fascia PUN corrente"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_corrente')
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
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
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Fascia corrente"

class PrezzoFasciaPUNSensorEntity(FasciaPUNSensorEntity):
    """Sensore che rappresenta il prezzo PUN della fascia corrente"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format('pun_prezzo_fascia_corrente')
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

    @property
    def state_class(self) -> str:
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self) -> str:
        return SensorDeviceClass.MONETARY

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
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Prezzo fascia corrente"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Restituisce gli attributi di stato"""
        state_attr = {
            ATTR_ROUNDED_DECIMALS: str(format(round(self.native_value, 3), '.3f'))
        }
        return state_attr