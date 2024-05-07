"""Coordinator for pun_sensor"""

# pylint: disable=W0613
from datetime import date, datetime, timedelta
import io
import logging
from statistics import mean
import zipfile
from zoneinfo import ZoneInfo

from aiohttp import ClientSession, ServerConnectionError

import holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACTUAL_DATA_ONLY,
    CONF_SCAN_HOUR,
    COORD_EVENT,
    DOMAIN,
    EVENT_UPDATE_FASCIA,
    EVENT_UPDATE_PUN,
    PUN_FASCIA_F1,
    PUN_FASCIA_F2,
    PUN_FASCIA_F3,
    PUN_FASCIA_F23,
    PUN_FASCIA_MONO,
)
from .utils import get_fascia, get_fascia_for_xml

_LOGGER = logging.getLogger(__name__)

tz_pun = ZoneInfo("Europe/Rome")


class PUNDataUpdateCoordinator(DataUpdateCoordinator):
    """Data coordinator"""

    session: ClientSession

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Gestione dell'aggiornamento da Home Assistant"""
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

        # Inizializza i valori di default
        self.web_retries = 0
        self.schedule_token = None
        self.pun = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.orari = [0, 0, 0, 0, 0]
        self.fascia_corrente: int | None = None
        self.fascia_successiva: int | None = None
        self.prossimo_cambio_fascia: datetime | None = None
        self.termine_prossima_fascia: datetime | None = None

        _LOGGER.debug(
            "Coordinator inizializzato (con 'usa dati reali' = %s).",
            self.actual_data_only,
        )

    async def _async_update_data(self):
        """Aggiornamento dati a intervalli prestabiliti"""

        # Calcola l'intervallo di date per il mese corrente
        date_end = dt_util.now().date()
        date_start = date(date_end.year, date_end.month, 1)

        # All'inizio del mese, aggiunge i valori del mese precedente
        # a meno che CONF_ACTUAL_DATA_ONLY non sia impostato
        if (not self.actual_data_only) and (date_end.day < 4):
            date_start = date_start - timedelta(days=3)

        start_date_param = str(date_start).replace("-", "")
        end_date_param = str(date_end).replace("-", "")

        # URL del sito Mercato elettrico
        download_url = f"https://gme.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload/downloadzipfile?DataInizio={start_date_param}&DataFine={end_date_param}&Date={end_date_param}&Mercato=MGP&Settore=Prezzi&FiltroDate=InizioFine"

        # imposta gli header della richiesta
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
            # aspetta la request
            bytes_response = await response.read()

            # se la richiesta NON e' andata a buon fine ritorna l'errore subito
            if response.status != 200:
                _LOGGER.error("Request Failed with code %s", response.status)
                raise ServerConnectionError(
                    f"Request failed with error {response.status}"
                )

            # la richiesta e' andata a buon fine, tenta l'estrazione
            try:
                archive = zipfile.ZipFile(io.BytesIO(bytes_response), "r")

            # Esce perché l'output non è uno ZIP, o ha un errore IO
            except (zipfile.BadZipfile, OSError) as e:  # not a zip:
                _LOGGER.error(
                    "Error failed download. url %s, length %s, response %s",
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

        # Carica le festività
        it_holidays = holidays.IT()

        # Inizializza le variabili di conteggio dei risultati
        mono = []
        f1 = []
        f2 = []
        f3 = []

        # Esamina ogni file XML nello ZIP (ordinandoli prima)
        for fn in sorted(archive.namelist()):
            # Scompatta il file XML in memoria
            xml_tree = et.parse(archive.open(fn))

            # Parsing dell'XML (1 file = 1 giorno)
            xml_root = xml_tree.getroot()

            # Estrae la data dal primo elemento (sarà identica per gli altri)
            dat_string = (
                xml_root.find("Prezzi").find("Data").text
            )  # YYYYMMDD # type: ignore

            # Converte la stringa giorno in data
            dat_date = date(
                int(dat_string[0:4]),  # type: ignore
                int(dat_string[4:6]),  # type: ignore
                int(dat_string[6:8]),  # type: ignore
            )

            # Verifica la festività
            festivo = dat_date in it_holidays

            # Estrae le rimanenti informazioni
            for prezzi in xml_root.iter("Prezzi"):
                # Estrae l'ora dall'XML
                ora = int(prezzi.find("Ora").text) - 1  # 1..24 # type: ignore

                # Estrae il prezzo PUN dall'XML in un float
                prezzo_string = prezzi.find("PUN").text  # type: ignore
                prezzo_string = prezzo_string.replace(".", "").replace(",", ".")  # type: ignore
                prezzo = float(prezzo_string) / 1000

                # Estrae la fascia oraria
                fascia = get_fascia_for_xml(dat_date, festivo, ora)

                # Calcola le statistiche
                mono.append(prezzo)
                match fascia:
                    case 3:
                        f3.append(prezzo)
                    case 2:
                        f2.append(prezzo)
                    case 1:
                        f1.append(prezzo)
                    case _:
                        pass

        # Salva i risultati nel coordinator
        self.orari[PUN_FASCIA_MONO] = len(mono)
        self.orari[PUN_FASCIA_F1] = len(f1)
        self.orari[PUN_FASCIA_F2] = len(f2)
        self.orari[PUN_FASCIA_F3] = len(f3)
        if self.orari[PUN_FASCIA_MONO] > 0:
            self.pun[PUN_FASCIA_MONO] = mean(mono)
        if self.orari[PUN_FASCIA_F1] > 0:
            self.pun[PUN_FASCIA_F1] = mean(f1)
        if self.orari[PUN_FASCIA_F2] > 0:
            self.pun[PUN_FASCIA_F2] = mean(f2)
        if self.orari[PUN_FASCIA_F3] > 0:
            self.pun[PUN_FASCIA_F3] = mean(f3)

        # Calcola la fascia F23 (a partire da F2 ed F3)
        # NOTA: la motivazione del calcolo è oscura ma sembra corretta; vedere:
        # https://github.com/virtualdj/pun_sensor/issues/24#issuecomment-1829846806
        if (self.orari[PUN_FASCIA_F2] and self.orari[PUN_FASCIA_F3]) > 0:
            # Esistono dati sia per F2 che per F3
            self.orari[PUN_FASCIA_F23] = (
                self.orari[PUN_FASCIA_F2] + self.orari[PUN_FASCIA_F3]
            )
            self.pun[PUN_FASCIA_F23] = (
                0.46 * self.pun[PUN_FASCIA_F2] + 0.54 * self.pun[PUN_FASCIA_F3]
            )
        else:
            # Devono esserci dati sia per F2 che per F3 affinché il risultato sia valido
            self.orari[PUN_FASCIA_F23] = 0
            self.pun[PUN_FASCIA_F23] = 0

        # Logga i dati
        _LOGGER.debug("Numero di dati: " + ", ".join(str(i) for i in self.orari))
        _LOGGER.debug("Valori PUN: " + ", ".join(str(f) for f in self.pun))
        return

    async def update_fascia(self, now=None):
        """Aggiorna la fascia oraria corrente"""

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
            "Nuova fascia corrente: F%s (prossima: F%s)",
            self.fascia_corrente,
            self.fascia_successiva,
            self.prossimo_cambio_fascia.strftime("%a %d/%m/%Y %H:%M:%S %z"),
        )

        # Notifica che i dati sono stati aggiornati (fascia)
        self.async_set_updated_data({COORD_EVENT: EVENT_UPDATE_FASCIA})

        # Schedula la prossima esecuzione
        async_track_point_in_time(
            self.hass, self.update_fascia, self.prossimo_cambio_fascia
        )

    async def update_pun(self, now=None):
        """Aggiorna i prezzi PUN da Internet (funziona solo se schedulata)"""
        # Aggiorna i dati da web
        try:
            # Esegue l'aggiornamento
            await self._async_update_data()

            # Se non ci sono eccezioni, ha avuto successo
            self.web_retries = 0
        # errore nel fetch dei dati
        except ServerConnectionError as e:
            # Errori durante l'esecuzione dell'aggiornamento, riprova dopo
            if self.web_retries == 0:
                # Primo errore, riprova dopo 1 minuto
                self.web_retries = 5
                retry_in_minutes = 1
            elif self.web_retries == 5:
                # Secondo errore, riprova dopo 10 minuti
                self.web_retries -= 1
                retry_in_minutes = 10
            elif self.web_retries == 1:
                # Ultimo errore, tentativi esauriti
                self.web_retries = 0

                # Schedula al giorno dopo
                retry_in_minutes = 0
            else:
                # Ulteriori errori (4, 3, 2)
                self.web_retries -= 1
                retry_in_minutes = 60 * (4 - self.web_retries)

            # Annulla eventuali schedulazioni attive
            if self.schedule_token is not None:
                self.schedule_token()
                self.schedule_token = None

            # Prepara la schedulazione
            if retry_in_minutes > 0:
                # Minuti dopo
                _LOGGER.warn(
                    "Errore durante l'aggiornamento via web, nuovo tentativo tra %s minut%s.",
                    retry_in_minutes,
                    "o" if retry_in_minutes == 1 else "i",
                    exc_info=e,
                )
                self.schedule_token = async_call_later(
                    self.hass, timedelta(minutes=retry_in_minutes), self.update_pun
                )
            else:
                # Giorno dopo
                _LOGGER.error(
                    "Errore durante l'aggiornamento via web, tentativi esauriti.",
                    exc_info=e,
                )
                next_update_pun = dt_util.now().replace(
                    hour=self.scan_hour, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                self.schedule_token = async_track_point_in_time(
                    self.hass, self.update_pun, next_update_pun
                )
                _LOGGER.debug(
                    "Prossimo aggiornamento web: %s",
                    next_update_pun.strftime("%d/%m/%Y %H:%M:%S %z"),
                )
            # Esce e attende la prossima schedulazione
            return

        # pylint: disable=W0718
        # Broad Except catching
        # possibili errori: estrazione dei dati, file non zip.
        # Non ha avuto errori nel download, da gestire diversamente, per ora schedula a domani
        # #TODO Wrap XML extracion into try/catch to re-raise into something we can expect
        except (Exception, UpdateFailed) as e:
            # Giorno dopo
            # Annulla eventuali schedulazioni attive
            self.clean_tokens()

            _LOGGER.error(
                "Errore durante l'estrazione dei dati",
                exc_info=e,
            )

            next_update_pun = get_next_date(
                dt_util.now(time_zone=tz_pun), self.scan_hour, 1
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
        next_update_pun = dt_util.now().replace(
            hour=self.scan_hour, minute=0, second=0, microsecond=0
        )
        if next_update_pun <= dt_util.now():
            # Se l'evento è già trascorso la esegue domani alla stessa ora
            next_update_pun = next_update_pun + timedelta(days=1)

        # Annulla eventuali schedulazioni attive
        if self.schedule_token is not None:
            self.schedule_token()
            self.schedule_token = None

        # Schedula la prossima esecuzione
        self.schedule_token = async_track_point_in_time(
            self.hass, self.update_pun, next_update_pun
        )
        _LOGGER.debug(
            "Prossimo aggiornamento web: %s",
            next_update_pun.strftime("%d/%m/%Y %H:%M:%S %z"),
        )
