"""Implementazione sensori di pun_sensor."""

import logging
from typing import Any

from awesomeversion.awesomeversion import AwesomeVersion

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoredExtraData,
    RestoreEntity,
)
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PUNDataUpdateCoordinator
from .const import (
    COORD_EVENT,
    DOMAIN,
    EVENT_UPDATE_FASCIA,
    EVENT_UPDATE_PREZZO_ZONALE,
    EVENT_UPDATE_PUN,
)
from .interfaces import Fascia, PunValues, PunValuesMP
from .utils import datetime_to_packed_string, get_next_date

ATTR_PREFIX_PREZZO_OGGI = "oggi_h_"
ATTR_PREFIX_PREZZO_DOMANI = "domani_h_"

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Inizializza e crea i sensori."""

    # Restituisce il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Crea i sensori dei valori del pun (legati al coordinator)
    entities: list[SensorEntity] = []
    entities.extend(
        PUNSensorEntity(coordinator, fascia) for fascia in PunValues().value
    )
    entities.extend(
        PUNSensorEntity(coordinator, fascia) for fascia in PunValuesMP().value
    )

    # Crea sensori aggiuntivi
    entities.append(FasciaPUNSensorEntity(coordinator))
    entities.append(PrezzoFasciaPUNSensorEntity(coordinator))
    entities.append(PrezzoZonaleSensorEntity(coordinator))
    entities.append(PUNOrarioSensorEntity(coordinator))

    # Aggiunge i sensori ma non aggiorna automaticamente via web
    # per lasciare il tempo ad Home Assistant di avviarsi
    async_add_entities(entities, update_before_add=False)


class PUNSensorEntity(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Sensore PUN relativo al prezzo medio mensile per fasce."""

    def __init__(self, coordinator: PUNDataUpdateCoordinator, fascia: Fascia) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator
        self.fascia = fascia

        # ID univoco sensore basato su un nome fisso
        match self.fascia:
            case Fascia.MONO:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_mono_orario")
            case Fascia.F1:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f1")
            case Fascia.F2:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f2")
            case Fascia.F3:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f3")
            case Fascia.F23:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f23")
            case Fascia.MONO_MP:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_mono_orario_mp")
            case Fascia.F1_MP:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f1_mp")
            case Fascia.F2_MP:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f2_mp")
            case Fascia.F3_MP:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f3_mp")
            case Fascia.F23_MP:
                self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_f23_mp")
            case _:
                self.entity_id = None
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 6
        self._available = False
        self._native_value = 0

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator."""

        # Identifica l'evento che ha scatenato l'aggiornamento
        if self.coordinator.data is None:
            return
        if (coordinator_event := self.coordinator.data.get(COORD_EVENT)) is None:
            return

        # Aggiorna il sensore in caso di variazione di prezzi
        if coordinator_event != EVENT_UPDATE_PUN:
            return

        if self.fascia != Fascia.F23 and self.fascia != Fascia.F23_MP:
            # Tutte le fasce tranne F23
            if "_MP" not in self.fascia.value:
                if len(self.coordinator.pun_data.pun[self.fascia]) > 0:
                    # Ci sono dati, sensore disponibile
                    self._available = True
                    self._native_value = self.coordinator.pun_values.value[self.fascia]
                else:
                    # Non ci sono dati, sensore non disponibile
                    self._available = False
            elif "_MP" in self.fascia.value:
                if len(self.coordinator.pun_data_mp.pun[self.fascia]) > 0:
                    # Ci sono dati, sensore disponibile
                    self._available = True
                    self._native_value = self.coordinator.pun_values_mp.value[self.fascia]
                else:
                    # Non ci sono dati, sensore non disponibile
                    self._available = False
        elif (
            len(self.coordinator.pun_data.pun[Fascia.F2])
            and len(self.coordinator.pun_data.pun[Fascia.F3])
        ) > 0 and self.fascia == Fascia.F23:
            # Caso speciale per fascia F23: affinché sia disponibile devono
            # esserci dati sia sulla fascia F2 che sulla F3,
            # visto che è calcolata a partire da questi
            self._available = True
            self._native_value = self.coordinator.pun_values.value[self.fascia]
        elif (
            len(self.coordinator.pun_data_mp.pun[Fascia.F2_MP])
            and len(self.coordinator.pun_data_mp.pun[Fascia.F3_MP])
        ) > 0 and self.fascia == Fascia.F23_MP:
            # Caso speciale per fascia F23: affinché sia disponibile devono
            # esserci dati sia sulla fascia F2 che sulla F3,
            # visto che è calcolata a partire da questi
            self._available = True
            self._native_value = self.coordinator.pun_values_mp.value[self.fascia]
        else:
            # Non ci sono dati, sensore non disponibile
            self._available = False

        # Aggiorna lo stato di Home Assistant
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo."""
        return RestoredExtraData(
            {"native_value": self._native_value if self._available else None}
        )

    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant."""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste
        if (old_data := await self.async_get_last_extra_data()) is not None:
            if (old_native_value := old_data.as_dict().get("native_value")) is not None:
                self._available = True
                self._native_value = old_native_value

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico."""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile."""
        return self._available

    @property
    def native_value(self) -> float:
        """Valore corrente del sensore."""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura."""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend."""
        return "mdi:chart-line"

    @property
    def name(self) -> str | None:
        """Restituisce il nome del sensore."""
        if self.fascia == Fascia.MONO:
            return "PUN mono-orario"
        if self.fascia == Fascia.MONO_MP:
            return "PUN mono-orario mese precedente"
        if self.fascia and "_MP" not in str(self.fascia.value):
            return f"PUN fascia {self.fascia.value}"
        if self.fascia and "_MP" in str(self.fascia.value):
            return f"PUN fascia {self.fascia.value.replace("_MP","")} mese precedente"
        return None


class FasciaPUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore che rappresenta il nome la fascia oraria PUN corrente."""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)

        # Inizializza coordinator
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format("pun_fascia_corrente")
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator."""

        # Identifica l'evento che ha scatenato l'aggiornamento
        if self.coordinator.data is None:
            return
        if (coordinator_event := self.coordinator.data.get(COORD_EVENT)) is None:
            return

        # Aggiorna il sensore in caso di variazione di fascia
        if coordinator_event != EVENT_UPDATE_FASCIA:
            return

        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico."""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile."""
        return self.coordinator.fascia_corrente is not None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Classe del sensore."""
        return SensorDeviceClass.ENUM

    @property
    def options(self) -> list[str] | None:
        """Possibili stati del sensore."""
        return [Fascia.F1.value, Fascia.F2.value, Fascia.F3.value]

    @property
    def native_value(self) -> str | None:
        """Restituisce la fascia corrente come stato."""
        if not self.coordinator.fascia_corrente:
            return None
        return self.coordinator.fascia_corrente.value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attributi aggiuntivi del sensore."""
        return {
            "fascia_successiva": self.coordinator.fascia_successiva.value
            if self.coordinator.fascia_successiva
            else None,
            "inizio_fascia_successiva": self.coordinator.prossimo_cambio_fascia,
            "termine_fascia_successiva": self.coordinator.termine_prossima_fascia,
        }

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend."""
        return "mdi:timeline-clock-outline"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore."""
        return "Fascia corrente"


class PrezzoFasciaPUNSensorEntity(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Sensore che rappresenta il prezzo PUN della fascia corrente."""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)

        # Inizializza coordinator
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format("pun_prezzo_fascia_corrente")
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 6
        self._available = False
        self._native_value = 0
        self._friendly_name = "Prezzo fascia corrente"

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator."""

        # Identifica l'evento che ha scatenato l'aggiornamento
        if self.coordinator.data is None:
            return
        if (coordinator_event := self.coordinator.data.get(COORD_EVENT)) is None:
            return

        # Aggiorna il sensore in caso di variazione di prezzi o di fascia
        if coordinator_event not in (EVENT_UPDATE_PUN, EVENT_UPDATE_FASCIA):
            return

        if self.coordinator.fascia_corrente is not None:
            self._available = (
                len(self.coordinator.pun_data.pun[self.coordinator.fascia_corrente]) > 0
            )
            self._native_value = self.coordinator.pun_values.value[
                self.coordinator.fascia_corrente
            ]
            self._friendly_name = (
                f"Prezzo fascia corrente ({self.coordinator.fascia_corrente.value})"
            )
        else:
            self._available = False
            self._native_value = 0
            self._friendly_name = "Prezzo fascia corrente"
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo."""
        return RestoredExtraData(
            {
                "native_value": self._native_value if self._available else None,
                "friendly_name": self._friendly_name if self._available else None,
            }
        )

    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant."""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste
        if (old_data := await self.async_get_last_extra_data()) is not None:
            if (old_native_value := old_data.as_dict().get("native_value")) is not None:
                self._available = True
                self._native_value = old_native_value
            if (
                old_friendly_name := old_data.as_dict().get("friendly_name")
            ) is not None:
                self._friendly_name = old_friendly_name

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico."""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile."""
        return self._available

    @property
    def native_value(self) -> float:
        """Restituisce il prezzo della fascia corrente."""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura."""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend."""
        return "mdi:currency-eur"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore."""
        return self._friendly_name


class PrezzoZonaleSensorEntity(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Sensore del prezzo zonale aggiornato ogni ora."""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format("pun_prezzo_zonale")
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 6
        self._available: bool = False
        self._native_value: float = 0
        self._friendly_name: str = "Prezzo zonale"
        self._prezzi_zonali: dict[str, float | None] = {}

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator."""

        # Identifica l'evento che ha scatenato l'aggiornamento
        if self.coordinator.data is None:
            return
        if (coordinator_event := self.coordinator.data.get(COORD_EVENT)) is None:
            return

        # Aggiornata la zona e/o i prezzi
        if coordinator_event == EVENT_UPDATE_PUN:
            if self.coordinator.pun_data.zona is not None:
                # Imposta il nome della zona
                self._friendly_name = (
                    f"Prezzo zonale ({self.coordinator.pun_data.zona.value})"
                )
                # Verifica che il coordinator abbia i prezzi
                if self.coordinator.pun_data.prezzi_zonali:
                    # Copia i dati dal coordinator in locale (per il backup)
                    self._prezzi_zonali = dict(self.coordinator.pun_data.prezzi_zonali)
            else:
                # Nessuna zona impostata
                self._friendly_name = "Prezzo zonale"
                self._prezzi_zonali = {}
                self._available = False
                self.async_write_ha_state()
                return

        # Cambiato l'orario del prezzo
        if coordinator_event in (EVENT_UPDATE_PUN, EVENT_UPDATE_PREZZO_ZONALE):
            if self.coordinator.pun_data.zona is not None:
                # Controlla se il prezzo orario esiste per l'ora corrente
                if (
                    datetime_to_packed_string(self.coordinator.orario_prezzo)
                    in self._prezzi_zonali
                ):
                    # Aggiorna il valore al prezzo orario
                    if (
                        valore := self._prezzi_zonali[
                            datetime_to_packed_string(self.coordinator.orario_prezzo)
                        ]
                    ) is not None:
                        self._native_value = valore
                        self._available = True
                    else:
                        # Prezzo non disponibile
                        self._available = False
                else:
                    # Orario non disponibile
                    self._available = False
            else:
                # Nessuna zona impostata
                self._available = False

        # Aggiorna lo stato di Home Assistant
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo."""

        # Salva i dati per la prossima istanza
        return RestoredExtraData(
            {
                "friendly_name": self._friendly_name if self._available else None,
                "zona": self.coordinator.pun_data.zona.name
                if self.coordinator.pun_data.zona is not None
                else None,
                "prezzi_zonali": self._prezzi_zonali,
            }
        )

    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant."""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste
        if (old_data := await self.async_get_last_extra_data()) is not None:
            # Recupera il dizionario con i valori precedenti
            old_data_dict = old_data.as_dict()

            # Zona geografica
            if (old_zona_str := old_data_dict.get("zona")) is not None:
                # Verifica che la zona attuale sia disponibile
                # (se non lo è, c'è un errore nella configurazione)
                if self.coordinator.pun_data.zona is None:
                    _LOGGER.warning(
                        "La zona geografica memorizzata '%s' non sembra essere più valida.",
                        old_zona_str,
                    )
                    self._available = False
                    return

                # Controlla se la zona memorizzata è diversa dall'attuale
                if old_zona_str != self.coordinator.pun_data.zona.name:
                    _LOGGER.debug(
                        "Ignorati i dati precedenti, perché riferiti alla zona '%s' (anziché '%s').",
                        old_zona_str,
                        self.coordinator.pun_data.zona.name,
                    )
                    self._available = False
                    return

            # Nome
            if (old_friendly_name := old_data_dict.get("friendly_name")) is not None:
                self._friendly_name = old_friendly_name

            # Valori delle fasce orarie
            if (old_prezzi_zonali := old_data_dict.get("prezzi_zonali")) is not None:
                self._prezzi_zonali = old_prezzi_zonali

                # Controlla se il prezzo orario esiste per l'ora corrente
                if (
                    datetime_to_packed_string(self.coordinator.orario_prezzo)
                    in self._prezzi_zonali
                ):
                    # Aggiorna il valore al prezzo orario
                    if (
                        valore := self._prezzi_zonali[
                            datetime_to_packed_string(self.coordinator.orario_prezzo)
                        ]
                    ) is not None:
                        self._native_value = valore
                        self._available = True
                    else:
                        # Prezzo non disponibile
                        self._available = False
                else:
                    # Imposta come non disponibile
                    self._available = False

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico."""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile."""
        return self._available

    @property
    def native_value(self) -> float:
        """Valore corrente del sensore."""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura."""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend."""
        return "mdi:map-clock-outline"

    @property
    def name(self) -> str | None:
        """Restituisce il nome del sensore."""
        return self._friendly_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Restituisce gli attributi di stato."""

        # Crea il dizionario degli attributi
        attributes: dict[str, Any] = {}

        # Aggiunge i prezzi orari negli attributi, ora per ora
        if self.coordinator.pun_data.zona is not None:
            for h in range(24):
                # Prezzi di oggi
                data_oggi = get_next_date(
                    dataora=self.coordinator.orario_prezzo, ora=h, offset=0
                )
                attributes[ATTR_PREFIX_PREZZO_OGGI + f"{h:02d}"] = (
                    self._prezzi_zonali.get(datetime_to_packed_string(data_oggi))
                )

            for h in range(24):
                # Prezzi di domani
                data_domani = get_next_date(
                    dataora=self.coordinator.orario_prezzo, ora=h, offset=1
                )
                attributes[ATTR_PREFIX_PREZZO_DOMANI + f"{h:02d}"] = (
                    self._prezzi_zonali.get(datetime_to_packed_string(data_domani))
                )

        # Restituisce gli attributi
        return attributes


class PUNOrarioSensorEntity(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Sensore del prezzo PUN aggiornato ogni ora."""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format("pun_orario")
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 6
        self._available: bool = False
        self._native_value: float = 0
        self._friendly_name: str = "PUN orario"
        self._pun_orari: dict[str, float | None] = {}

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator."""

        # Identifica l'evento che ha scatenato l'aggiornamento
        if self.coordinator.data is None:
            return
        if (coordinator_event := self.coordinator.data.get(COORD_EVENT)) is None:
            return

        # Aggiornati i prezzi PUN
        if coordinator_event == EVENT_UPDATE_PUN:
            # Verifica che il coordinator abbia i prezzi
            if self.coordinator.pun_data.pun_orari:
                # Copia i dati dal coordinator in locale (per il backup)
                self._pun_orari = dict(self.coordinator.pun_data.pun_orari)

        # Cambiato l'orario del prezzo
        if coordinator_event in (EVENT_UPDATE_PUN, EVENT_UPDATE_PREZZO_ZONALE):
            # Controlla se il PUN orario esiste per l'ora corrente
            if (
                datetime_to_packed_string(self.coordinator.orario_prezzo)
                in self._pun_orari
            ):
                # Aggiorna il valore al prezzo orario
                if (
                    valore := self._pun_orari[
                        datetime_to_packed_string(self.coordinator.orario_prezzo)
                    ]
                ) is not None:
                    self._native_value = valore
                    self._available = True
                else:
                    # Prezzo non disponibile
                    self._available = False
            else:
                # Orario non disponibile
                self._available = False

        # Aggiorna lo stato di Home Assistant
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo."""

        # Salva i dati per la prossima istanza
        return RestoredExtraData(
            {
                "pun_orari": self._pun_orari,
            }
        )

    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant."""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste
        if (old_data := await self.async_get_last_extra_data()) is not None:
            # Recupera il dizionario con i valori precedenti
            old_data_dict = old_data.as_dict()

            # Valori dei prezzi orari
            if (old_pun_orari := old_data_dict.get("pun_orari")) is not None:
                self._pun_orari = old_pun_orari

                # Controlla se il prezzo orario esiste per l'ora corrente
                if (
                    datetime_to_packed_string(self.coordinator.orario_prezzo)
                    in self._pun_orari
                ):
                    # Aggiorna il valore al prezzo orario
                    if (
                        valore := self._pun_orari[
                            datetime_to_packed_string(self.coordinator.orario_prezzo)
                        ]
                    ) is not None:
                        self._native_value = valore
                        self._available = True
                    else:
                        # Prezzo non disponibile
                        self._available = False
                else:
                    # Imposta come non disponibile
                    self._available = False

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico."""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile."""
        return self._available

    @property
    def native_value(self) -> float:
        """Valore corrente del sensore."""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura."""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend."""
        if AwesomeVersion(HA_VERSION) < AwesomeVersion("2024.1.0"):
            return "mdi:receipt-clock-outline"
        return "mdi:invoice-clock-outline"

    @property
    def name(self) -> str | None:
        """Restituisce il nome del sensore."""
        return self._friendly_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Restituisce gli attributi di stato."""

        # Crea il dizionario degli attributi
        attributes: dict[str, Any] = {}

        # Aggiunge i prezzi orari negli attributi, ora per ora
        for h in range(24):
            # Prezzi di oggi
            data_oggi = get_next_date(
                dataora=self.coordinator.orario_prezzo, ora=h, offset=0
            )
            attributes[ATTR_PREFIX_PREZZO_OGGI + f"{h:02d}"] = self._pun_orari.get(
                datetime_to_packed_string(data_oggi)
            )

        for h in range(24):
            # Prezzi di domani
            data_domani = get_next_date(
                dataora=self.coordinator.orario_prezzo, ora=h, offset=1
            )
            attributes[ATTR_PREFIX_PREZZO_DOMANI + f"{h:02d}"] = self._pun_orari.get(
                datetime_to_packed_string(data_domani)
            )

        # Restituisce gli attributi
        return attributes
