"""Prezzi PUN del mese"""
from datetime import date, timedelta, datetime
import holidays
from statistics import mean
import zipfile, io
from bs4 import BeautifulSoup
import xml.etree.ElementTree as et
from typing import Tuple
from functools import partial
from utils import get_fascia, get_fascia_for_xml

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.event import async_track_point_in_time, async_call_later
from homeassistant.setup import SetupPhases, async_pause_setup
import homeassistant.util.dt as dt_util
from zoneinfo import ZoneInfo

from .const import (
    DOMAIN,
    PUN_FASCIA_MONO,
    PUN_FASCIA_F23,
    PUN_FASCIA_F1,
    PUN_FASCIA_F2,
    PUN_FASCIA_F3,
    CONF_SCAN_HOUR,
    CONF_ACTUAL_DATA_ONLY,
    COORD_EVENT,
    EVENT_UPDATE_FASCIA,
    EVENT_UPDATE_PUN
)

import logging
_LOGGER = logging.getLogger(__name__)

# Usa sempre il fuso orario italiano (i dati del sito sono per il mercato italiano)
tz_pun = ZoneInfo('Europe/Rome')

# Definisce i tipi di entità
PLATFORMS: list[str] = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Impostazione dell'integrazione da configurazione Home Assistant"""

    # Carica le dipendenze di holidays in background
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
    coordinator.schedule_token = async_call_later(hass, timedelta(seconds=10), coordinator.update_pun)

    # Registra il callback di modifica opzioni
    config.async_on_unload(config.add_update_listener(update_listener))
    return True

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Rimozione dell'integrazione da Home Assistant"""
    
    # Scarica i sensori (disabilitando di conseguenza il coordinator)
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)

    return unload_ok

async def update_listener(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Modificate le opzioni da Home Assistant"""

    # Recupera il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Aggiorna le impostazioni del coordinator dalle opzioni
    if config.options[CONF_SCAN_HOUR] != coordinator.scan_hour:
        # Modificata l'ora di scansione
        coordinator.scan_hour = config.options[CONF_SCAN_HOUR]

        # Calcola la data della prossima esecuzione (all'ora definita)
        next_update_pun = dt_util.now().replace(hour=coordinator.scan_hour,
                                minute=0, second=0, microsecond=0)
        if next_update_pun.hour < dt_util.now().hour:
            # Se l'ora impostata è minore della corrente, schedula a domani
            # (perciò se è uguale esegue subito l'aggiornamento)
            next_update_pun = next_update_pun + timedelta(days=1)

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None

        # Schedula la prossima esecuzione
        coordinator.web_retries = 0
        coordinator.schedule_token = async_track_point_in_time(coordinator.hass, coordinator.update_pun, next_update_pun)
        _LOGGER.debug('Prossimo aggiornamento web: %s', next_update_pun.strftime('%d/%m/%Y %H:%M:%S %z'))

    if config.options[CONF_ACTUAL_DATA_ONLY] != coordinator.actual_data_only:
        # Modificata impostazione 'Usa dati reali'
        coordinator.actual_data_only = config.options[CONF_ACTUAL_DATA_ONLY]
        _LOGGER.debug('Nuovo valore \'usa dati reali\': %s.', coordinator.actual_data_only)

        # Annulla eventuali schedulazioni attive
        if coordinator.schedule_token is not None:
            coordinator.schedule_token()
            coordinator.schedule_token = None

        # Esegue un nuovo aggiornamento immediatamente
        coordinator.web_retries = 0
        coordinator.schedule_token = async_call_later(coordinator.hass, timedelta(seconds=5), coordinator.update_pun)


class PUNDataUpdateCoordinator(DataUpdateCoordinator):
    session: ClientSession

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Gestione dell'aggiornamento da Home Assistant"""
        super().__init__(
            hass,
            _LOGGER,
            # Nome dei dati (a fini di log)
            name = DOMAIN,
            # Nessun update_interval (aggiornamento automatico disattivato)
        )

        # Salva la sessione client e la configurazione
        self.session = async_get_clientsession(hass)

        # Inizializza i valori di configurazione (dalle opzioni o dalla configurazione iniziale)
        self.actual_data_only = config.options.get(CONF_ACTUAL_DATA_ONLY, config.data[CONF_ACTUAL_DATA_ONLY])
        self.scan_hour = config.options.get(CONF_SCAN_HOUR, config.data[CONF_SCAN_HOUR])

        # Inizializza i valori di default
        self.web_retries = 0
        self.schedule_token = None
        self.pun = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.orari = [0, 0, 0, 0, 0]
        self.fascia_corrente = None
        _LOGGER.debug('Coordinator inizializzato (con \'usa dati reali\' = %s).', self.actual_data_only)

    async def _async_update_data(self):
        """Aggiornamento dati a intervalli prestabiliti"""
        
        # Calcola l'intervallo di date per il mese corrente
        date_end = dt_util.now().date()
        date_start = date(date_end.year, date_end.month, 1)

        # All'inizio del mese, aggiunge i valori del mese precedente
        # a meno che CONF_ACTUAL_DATA_ONLY non sia impostato
        if (not self.actual_data_only) and (date_end.day < 4):
            date_start = date_start - timedelta(days=3)

        # URL del sito Mercato elettrico
        LOGIN_URL = 'https://www.mercatoelettrico.org/It/Tools/Accessodati.aspx?ReturnUrl=%2fIt%2fdownload%2fDownloadDati.aspx%3fval%3dMGP_Prezzi&val=MGP_Prezzi'
        DOWNLOAD_URL = 'https://www.mercatoelettrico.org/It/download/DownloadDati.aspx?val=MGP_Prezzi'
        
        # Apre la pagina per generare i cookie e i campi nascosti
        _LOGGER.debug('Connessione a URL login.')
        async with self.session.get(LOGIN_URL) as response:
            soup = await self.hass.async_add_executor_job(
                partial(BeautifulSoup, await response.read(), features='html.parser')
            )
        
        # Recupera i campi nascosti __VIEWSTATE e __EVENTVALIDATION per la prossima richiesta
        viewstate = soup.find('input',{'name':'__VIEWSTATE'})['value']
        eventvalidation = soup.find('input',{'name':'__EVENTVALIDATION'})['value']
        login_payload = {
            'ctl00$ContentPlaceHolder1$CBAccetto1': 'on',
            'ctl00$ContentPlaceHolder1$CBAccetto2': 'on',
            'ctl00$ContentPlaceHolder1$Button1': 'Accetto',
            '__VIEWSTATE': viewstate,
            '__EVENTVALIDATION': eventvalidation
        }

        # Effettua il login (che se corretto porta alla pagina di download XML grazie al 'ReturnUrl')
        _LOGGER.debug('Invio credenziali a URL login.')
        async with self.session.post(LOGIN_URL, data=login_payload) as response:
            soup = await self.hass.async_add_executor_job(
                partial(BeautifulSoup, await response.read(), features='html.parser')
            )

        # Recupera i campi nascosti __VIEWSTATE per la prossima richiesta
        viewstate = soup.find('input',{'name':'__VIEWSTATE'})['value']    
        data_request_payload = {
            'ctl00$ContentPlaceHolder1$tbDataStart': date_start.strftime('%d/%m/%Y'),
            'ctl00$ContentPlaceHolder1$tbDataStop': date_end.strftime('%d/%m/%Y'),
            'ctl00$ContentPlaceHolder1$btnScarica': 'scarica+file+xml+compresso',
            '__VIEWSTATE': viewstate
        }

        # Effettua il download dello ZIP con i file XML
        _LOGGER.debug('Inizio download file ZIP con XML.')
        async with self.session.post(DOWNLOAD_URL, data=data_request_payload) as response:
            # Scompatta lo ZIP in memoria
            try:
                archive = zipfile.ZipFile(io.BytesIO(await response.read()))
            except:
                # Esce perché l'output non è uno ZIP
                raise UpdateFailed('Archivio ZIP scaricato dal sito non valido.')

        # Mostra i file nell'archivio
        _LOGGER.debug(f'{ len(archive.namelist()) } file trovati nell\'archivio (' + ', '.join(str(fn) for fn in archive.namelist()) + ').')

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
            dat_string = xml_root.find('Prezzi').find('Data').text #YYYYMMDD

            # Converte la stringa giorno in data
            dat_date = date(int(dat_string[0:4]), int(dat_string[4:6]), int(dat_string[6:8]))

            # Verifica la festività
            festivo = dat_date in it_holidays

            # Estrae le rimanenti informazioni
            for prezzi in xml_root.iter('Prezzi'):
                # Estrae l'ora dall'XML
                ora = int(prezzi.find('Ora').text) - 1 # 1..24
                
                # Estrae il prezzo PUN dall'XML in un float
                prezzo_string = prezzi.find('PUN').text
                prezzo_string = prezzo_string.replace('.','').replace(',','.')
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
        if self.orari[PUN_FASCIA_F2] > 0 and self.orari[PUN_FASCIA_F3] > 0:
            # Esistono dati sia per F2 che per F3
            self.orari[PUN_FASCIA_F23] = self.orari[PUN_FASCIA_F2] + self.orari[PUN_FASCIA_F3]
            self.pun[PUN_FASCIA_F23] = 0.46 * self.pun[PUN_FASCIA_F2] + 0.54 * self.pun[PUN_FASCIA_F3]
        else:
            # Devono esserci dati sia per F2 che per F3 affinché il risultato sia valido
            self.orari[PUN_FASCIA_F23] = 0
            self.pun[PUN_FASCIA_F23] = 0
       
        # Logga i dati
        _LOGGER.debug('Numero di dati: ' + ', '.join(str(i) for i in self.orari))
        _LOGGER.debug('Valori PUN: ' + ', '.join(str(f) for f in self.pun))
        return

    async def update_fascia(self, now=None):
        """Aggiorna la fascia oraria corrente"""

        # Scrive l'ora corrente (a scopi di debug)
        _LOGGER.debug('Ora corrente sistema: %s', dt_util.now().strftime('%a %d/%m/%Y %H:%M:%S %z'))
        _LOGGER.debug('Ora corrente fuso orario italiano: %s', dt_util.now(time_zone=tz_pun).strftime('%a %d/%m/%Y %H:%M:%S %z'))

        # Ottiene la fascia oraria corrente e il prossimo aggiornamento
        self.fascia_corrente, next_update_fascia = get_fascia(dt_util.now(time_zone=tz_pun))
        _LOGGER.info('Nuova fascia corrente: F%s (prossima: %s)', self.fascia_corrente, next_update_fascia.strftime('%a %d/%m/%Y %H:%M:%S %z'))

        # Notifica che i dati sono stati aggiornati (fascia)
        self.async_set_updated_data({ COORD_EVENT: EVENT_UPDATE_FASCIA })

        # Schedula la prossima esecuzione
        async_track_point_in_time(self.hass, self.update_fascia, next_update_fascia)

    async def update_pun(self, now=None):
        """Aggiorna i prezzi PUN da Internet (funziona solo se schedulata)"""

        # Aggiorna i dati da web
        try:
            # Esegue l'aggiornamento
            await self._async_update_data()

            # Se non ci sono eccezioni, ha avuto successo
            self.web_retries = 0
        except Exception as e:
            # Errori durante l'esecuzione dell'aggiornamento, riprova dopo
            if (self.web_retries == 0):
                # Primo errore, riprova dopo 1 minuto
                self.web_retries = 5
                retry_in_minutes = 1
            elif (self.web_retries == 5):
                # Secondo errore, riprova dopo 10 minuti
                self.web_retries -= 1
                retry_in_minutes = 10
            elif (self.web_retries == 1):
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
            if (retry_in_minutes > 0):
                # Minuti dopo
                _LOGGER.warn('Errore durante l\'aggiornamento via web, nuovo tentativo tra %s minut%s.', retry_in_minutes, 'o' if retry_in_minutes == 1 else 'i', exc_info=e)
                self.schedule_token = async_call_later(self.hass, timedelta(minutes=retry_in_minutes), self.update_pun)
            else:
                # Giorno dopo
                _LOGGER.error('Errore durante l\'aggiornamento via web, tentativi esauriti.', exc_info=e)
                next_update_pun = dt_util.now().replace(hour=self.scan_hour,
                                minute=0, second=0, microsecond=0) + timedelta(days=1)
                self.schedule_token = async_track_point_in_time(self.hass, self.update_pun, next_update_pun)
                _LOGGER.debug('Prossimo aggiornamento web: %s', next_update_pun.strftime('%d/%m/%Y %H:%M:%S %z'))
            
            # Esce e attende la prossima schedulazione
            return

        # Notifica che i dati PUN sono stati aggiornati con successo
        self.async_set_updated_data({ COORD_EVENT: EVENT_UPDATE_PUN })

        # Calcola la data della prossima esecuzione
        next_update_pun = dt_util.now().replace(hour=self.scan_hour,
                                minute=0, second=0, microsecond=0)
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
