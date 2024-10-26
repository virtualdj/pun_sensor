"""Prezzi PUN del mese."""

from datetime import timedelta
import logging
import random

from awesomeversion.awesomeversion import AwesomeVersion
import holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
import homeassistant.util.dt as dt_util

from .const import CONF_ACTUAL_DATA_ONLY, CONF_SCAN_HOUR, DOMAIN, WEB_RETRIES_MINUTES
from .coordinator import PUNDataUpdateCoordinator

if AwesomeVersion(HA_VERSION) >= AwesomeVersion("2024.5.0"):
    from homeassistant.setup import SetupPhases, async_pause_setup

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)

# Definisce i tipi di entità
PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Impostazione dell'integrazione da configurazione Home Assistant."""

    # Carica le dipendenze di holidays in background per evitare errori nel log
    if AwesomeVersion(HA_VERSION) >= AwesomeVersion("2024.5.0"):
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            await hass.async_add_import_executor_job(holidays.IT)

    # Salva il coordinator nella configurazione
    coordinator = PUNDataUpdateCoordinator(hass, config)
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator

    # Aggiorna immediatamente la fascia oraria corrente
    await coordinator.update_fascia()

    # Crea i sensori con la configurazione specificata
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)

    # Schedula l'aggiornamento via web 10 secondi dopo l'avvio
    coordinator.schedule_token = async_call_later(
        hass, timedelta(seconds=10), coordinator.update_pun
    )

    # Registra il callback di modifica opzioni
    config.async_on_unload(config.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Rimozione dell'integrazione da Home Assistant."""

    # Scarica i sensori (disabilitando di conseguenza il coordinator)
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Modificate le opzioni da Home Assistant."""

    # Recupera il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Aggiorna le impostazioni del coordinator dalle opzioni
    if config.options[CONF_SCAN_HOUR] != coordinator.scan_hour:
        # Modificata l'ora di scansione
        coordinator.scan_hour = config.options[CONF_SCAN_HOUR]

        # Calcola la data della prossima esecuzione (all'ora definita)
        now = dt_util.now()

        # Aggiunge un numero random di minuti alla call per evitare di sovraccaricare i server API
        randminute = random.randrange(0, 59)
        next_update_pun = now.replace(
            hour=coordinator.scan_hour, minute=randminute, second=0, microsecond=0
        )
        if next_update_pun.hour < now.hour:
            # Se l'ora impostata è minore della corrente, schedula a domani
            # (perciò se è uguale esegue subito l'aggiornamento)
            next_update_pun = next_update_pun + timedelta(days=1)

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None

        # Schedula la prossima esecuzione
        coordinator.web_retries = WEB_RETRIES_MINUTES
        coordinator.schedule_token = async_track_point_in_time(
            coordinator.hass, coordinator.update_pun, next_update_pun
        )
        _LOGGER.debug(
            "Prossimo aggiornamento web: %s",
            next_update_pun.strftime("%d/%m/%Y %H:%M:%S %z"),
        )

    if config.options[CONF_ACTUAL_DATA_ONLY] != coordinator.actual_data_only:
        # Modificata impostazione 'Usa dati reali'
        coordinator.actual_data_only = config.options[CONF_ACTUAL_DATA_ONLY]
        _LOGGER.debug(
            "Nuovo valore 'usa dati reali': %s.", coordinator.actual_data_only
        )

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None

        # Esegue un nuovo aggiornamento immediatamente
        coordinator.web_retries = WEB_RETRIES_MINUTES
        coordinator.schedule_token = async_call_later(
            coordinator.hass, timedelta(seconds=5), coordinator.update_pun
        )
