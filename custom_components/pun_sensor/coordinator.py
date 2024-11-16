"""Coordinator per pun_sensor."""

from datetime import date, datetime, timedelta
import io
import logging
import random
from statistics import mean
import zipfile

from aiohttp import ClientSession, ServerConnectionError
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACTUAL_DATA_ONLY,
    CONF_SCAN_HOUR,
    CONF_SCAN_MINUTE,
    COORD_EVENT,
    DOMAIN,
    EVENT_UPDATE_FASCIA,
    EVENT_UPDATE_PUN,
    WEB_RETRIES_MINUTES,
)
from .interfaces import Fascia, PunData, PunValues
from .utils import extract_xml, get_fascia, get_next_date

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)

# Usa sempre il fuso orario italiano (i dati del sito sono per il mercato italiano)
tz_pun = ZoneInfo("Europe/Rome")


class PUNDataUpdateCoordinator(DataUpdateCoordinator):
    """Classe coordinator di aggiornamento dati."""

    session: ClientSession

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Gestione dell'aggiornamento da Home Assistant."""
        super().__init__(
            hass,
            _LOGGER,
            # Nome dei dati (a fini di log)
            name=DOMAIN,
            # Nessun update_interval (aggiornamento automatico disattivato)
        )

        # Salva la sessione client e la configurazione
        self.session = async_get_clientsession(hass)

        # Inizializza i valori di configurazione (dalle opzioni o dalla configurazione iniziale)
        self.actual_data_only = config.options.get(
            CONF_ACTUAL_DATA_ONLY, config.data[CONF_ACTUAL_DATA_ONLY]
        )
        self.scan_hour = config.options.get(CONF_SCAN_HOUR, config.data[CONF_SCAN_HOUR])

        # Carica il minuto di esecuzione dalla configurazione (o lo crea se non esiste)
        self.scan_minute = 0
        self.update_scan_minutes_from_config(hass=hass, config=config, new_minute=False)

        # Inizializza i valori di default
        self.web_retries = WEB_RETRIES_MINUTES
        self.schedule_token = None
        self.pun_data: PunData = PunData()
        self.pun_values: PunValues = PunValues()
        self.fascia_corrente: Fascia | None = None
        self.fascia_successiva: Fascia | None = None
        self.prossimo_cambio_fascia: datetime | None = None
        self.termine_prossima_fascia: datetime | None = None

        _LOGGER.debug(
            "Coordinator inizializzato (con 'usa dati reali' = %s).",
            self.actual_data_only,
        )

    def clean_tokens(self):
        """Annulla eventuali schedulazioni attive."""
        if self.schedule_token is not None:
            self.schedule_token()
            self.schedule_token = None

    def update_scan_minutes_from_config(
        self, hass: HomeAssistant, config: ConfigEntry, new_minute: bool = False
    ):
        """Imposta il minuto di aggiornamento nell'ora configurata.

        Determina casualmente in quale minuto eseguire l'aggiornamento web
        per evitare che le integrazioni di tutti gli utenti richiamino le API nello
        stesso momento, a parità di ora.
        """

        # Controlla se estrarre a caso i minuti
        if new_minute or (CONF_SCAN_MINUTE not in config.data):
            # Genera un minuto casuale e lo inserisce nella configurazione
            self.scan_minute = random.randint(0, 59)
            new_data = {
                **config.data,
                CONF_SCAN_MINUTE: self.scan_minute,
            }

            @callback
            def async_update_entry() -> None:
                """Aggiorna la configurazione con i nuovi dati."""
                self.hass.config_entries.async_update_entry(config, data=new_data)

            # Accoda l'esecuzione del salvataggio dell'impostazione
            hass.add_job(async_update_entry)
        else:
            # Carica i minuti dalla configurazione
            self.scan_minute = config.data.get(CONF_SCAN_MINUTE, 0)

    async def _async_update_data(self):
        """Aggiornamento dati a intervalli prestabiliti."""

        # Calcola l'intervallo di date per il mese corrente
        date_end = dt_util.now().date()
        date_start = date(date_end.year, date_end.month, 1)

        # All'inizio del mese, aggiunge i valori del mese precedente
        # a meno che CONF_ACTUAL_DATA_ONLY non sia impostato
        if (not self.actual_data_only) and (date_end.day < 4):
            date_start = date_start - timedelta(days=3)

        start_date_param = date_start.strftime("%Y%m%d")
        end_date_param = date_end.strftime("%Y%m%d")

        # URL del sito Mercato elettrico
        download_url = f"https://gme.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload/downloadzipfile?DataInizio={start_date_param}&DataFine={end_date_param}&Date={end_date_param}&Mercato=MGP&Settore=Prezzi&FiltroDate=InizioFine"

        # Imposta gli header della richiesta
        heads = {
            "moduleid": "12103",
            "referrer": "https://gme.mercatoelettrico.org/en-us/Home/Results/Electricity/MGP/Download?valore=Prezzi",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "tabid": "1749",
            "userid": "-1",
        }

        # Effettua il download dello ZIP con i file XML
        _LOGGER.debug("Inizio download file ZIP con XML.")
        async with self.session.get(download_url, headers=heads) as response:
            # Aspetta la request
            bytes_response = await response.read()

            # Se la richiesta NON e' andata a buon fine ritorna l'errore subito
            if response.status != 200:
                _LOGGER.error("Richiesta fallita con errore %s", response.status)
                raise ServerConnectionError(
                    f"Richiesta fallita con errore {response.status}"
                )

            # La richiesta e' andata a buon fine, tenta l'estrazione
            try:
                archive = zipfile.ZipFile(io.BytesIO(bytes_response), "r")

            # Ritorna error se l'output non è uno ZIP, o ha un errore IO
            except (zipfile.BadZipfile, OSError) as e:  # not a zip:
                _LOGGER.error(
                    "Download fallito con URL: %s, lunghezza %s, risposta %s",
                    download_url,
                    response.content_length,
                    response.status,
                )
                raise UpdateFailed("Archivio ZIP scaricato dal sito non valido.") from e

        # Mostra i file nell'archivio
        _LOGGER.debug(
            "%s file trovati nell'archivio (%s)",
            len(archive.namelist()),
            ", ".join(str(fn) for fn in archive.namelist()),
        )

        # Estrae i dati dall'archivio
        self.pun_data = extract_xml(archive, self.pun_data)

        # Per ogni fascia, calcola il valore del pun
        for fascia, value_list in self.pun_data.pun.items():
            # Se abbiamo valori nella fascia
            if len(value_list) > 0:
                # Calcola la media dei pun e aggiorna il valore del pun attuale
                # per la fascia corrispondente
                self.pun_values.value[fascia] = mean(self.pun_data.pun[fascia])
            else:
                # Skippiamo i dict se vuoti
                pass

        # Calcola la fascia F23 (a partire da F2 ed F3)
        # NOTA: la motivazione del calcolo è oscura ma sembra corretta; vedere:
        # https://github.com/virtualdj/pun_sensor/issues/24#issuecomment-1829846806
        if (
            len(self.pun_data.pun[Fascia.F2]) and len(self.pun_data.pun[Fascia.F3])
        ) > 0:
            self.pun_values.value[Fascia.F23] = (
                0.46 * self.pun_values.value[Fascia.F2]
                + 0.54 * self.pun_values.value[Fascia.F3]
            )
        else:
            self.pun_values.value[Fascia.F23] = 0

        # Logga i dati
        _LOGGER.debug(
            "Numero di dati: %s",
            ", ".join(
                str(f"{len(dati)} ({fascia.value})")
                for fascia, dati in self.pun_data.pun.items()
                if fascia != Fascia.F23
            ),
        )
        _LOGGER.debug(
            "Valori PUN: %s",
            ", ".join(
                f"{prezzo} ({fascia.value})"
                for fascia, prezzo in self.pun_values.value.items()
            ),
        )

    async def update_fascia(self, now=None):
        """Aggiorna la fascia oraria corrente."""

        # Scrive l'ora corrente (a scopi di debug)
        _LOGGER.debug(
            "Ora corrente sistema: %s",
            dt_util.now().strftime("%a %d/%m/%Y %H:%M:%S %z"),
        )
        _LOGGER.debug(
            "Ora corrente fuso orario italiano: %s",
            dt_util.now(time_zone=tz_pun).strftime("%a %d/%m/%Y %H:%M:%S %z"),
        )

        # Ottiene la fascia oraria corrente e il prossimo aggiornamento
        self.fascia_corrente, self.prossimo_cambio_fascia = get_fascia(
            dt_util.now(time_zone=tz_pun)
        )

        # Calcola la fascia futura ri-applicando lo stesso algoritmo
        self.fascia_successiva, self.termine_prossima_fascia = get_fascia(
            self.prossimo_cambio_fascia
        )
        _LOGGER.info(
            "Nuova fascia corrente: %s (prossima: %s alle %s)",
            self.fascia_corrente.value,
            self.fascia_successiva.value,
            self.prossimo_cambio_fascia.strftime("%a %d/%m/%Y %H:%M:%S %z"),
        )

        # Notifica che i dati sono stati aggiornati (fascia)
        self.async_set_updated_data({COORD_EVENT: EVENT_UPDATE_FASCIA})

        # Schedula la prossima esecuzione
        async_track_point_in_time(
            self.hass, self.update_fascia, self.prossimo_cambio_fascia
        )

    async def update_pun(self, now=None):
        """Aggiorna i prezzi PUN da Internet (funziona solo se schedulata)."""
        # Aggiorna i dati da web
        try:
            # Esegue l'aggiornamento
            await self._async_update_data()

            # Se non ci sono eccezioni, ha avuto successo
            # Ricarica i tentativi per la prossima esecuzione
            self.web_retries = WEB_RETRIES_MINUTES

        # Errore nel fetch dei dati se la response non e' 200
        # pylint: disable=broad-exception-caught
        except (Exception, UpdateFailed, ServerConnectionError) as e:
            # Errori durante l'esecuzione dell'aggiornamento, riprova dopo
            # Annulla eventuali schedulazioni attive
            self.clean_tokens()

            # Prepara la schedulazione
            if self.web_retries:
                # Minuti dopo
                retry_in_minutes = self.web_retries.pop(0)
                _LOGGER.warning(
                    "Errore durante l'aggiornamento dei dati, nuovo tentativo tra %s minut%s.",
                    retry_in_minutes,
                    "o" if retry_in_minutes == 1 else "i",
                    exc_info=e,
                )
                self.schedule_token = async_call_later(
                    self.hass, timedelta(minutes=retry_in_minutes), self.update_pun
                )
            else:
                # Tentativi esauriti, passa al giorno dopo
                _LOGGER.error(
                    "Errore durante l'aggiornamento via web, tentativi esauriti.",
                    exc_info=e,
                )
                next_update_pun = get_next_date(
                    dataora=dt_util.now(time_zone=tz_pun),
                    ora=self.scan_hour,
                    minuto=self.scan_minute,
                    offset=1,
                )
                self.schedule_token = async_track_point_in_time(
                    self.hass, self.update_pun, next_update_pun
                )
                _LOGGER.debug(
                    "Prossimo aggiornamento web: %s",
                    next_update_pun.strftime("%d/%m/%Y %H:%M:%S %z"),
                )

            # Esce e attende la prossima schedulazione
            return

        # Notifica che i dati PUN sono stati aggiornati con successo
        self.async_set_updated_data({COORD_EVENT: EVENT_UPDATE_PUN})

        # Calcola la data della prossima esecuzione
        next_update_pun = get_next_date(
            dataora=dt_util.now(time_zone=tz_pun),
            ora=self.scan_hour,
            minuto=self.scan_minute,
        )
        if next_update_pun <= dt_util.now():
            # Se l'evento è già trascorso, passa a domani alla stessa ora
            next_update_pun = next_update_pun + timedelta(days=1)

        # Annulla eventuali schedulazioni attive
        self.clean_tokens()

        # Schedula la prossima esecuzione
        self.schedule_token = async_track_point_in_time(
            self.hass, self.update_pun, next_update_pun
        )
        _LOGGER.debug(
            "Prossimo aggiornamento web: %s",
            next_update_pun.strftime("%d/%m/%Y %H:%M:%S %z"),
        )
