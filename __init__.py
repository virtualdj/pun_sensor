"""Prezzi mensili PUN"""
from datetime import date, timedelta, datetime
import holidays
from statistics import mean
import zipfile, io
from bs4 import BeautifulSoup
import xml.etree.ElementTree as et

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.discovery import async_load_platform

from .const import (
    DOMAIN,
    PUN_FASCIA_MONO,
    PUN_FASCIA_F1,
    PUN_FASCIA_F2,
    PUN_FASCIA_F3,
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up PUN prices from a config entry"""
    conf = config[DOMAIN]
    coordinator = PUNDataUpdateCoordinator(hass, config)

    # Aggiorna i dati iniziali per quando verrano aggiunte le entità
    await coordinator.async_refresh()

    # Salva i riferimenti al coordinator
    hass.data[DOMAIN] = {
        "conf": conf,
        "coordinator": coordinator,
    }

    # Crea le entità
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True

class PUNDataUpdateCoordinator(DataUpdateCoordinator):
    session: ClientSession

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """ Gestione dell'aggiornamento da Home Assistant """
        super().__init__(
            hass,
            _LOGGER,
            # Nome dei dati (a fini di log)
            name = DOMAIN,

            # Intervallo di aggiornamento
            update_interval=timedelta(seconds=10)
        )

        # Salva la sessione client e la configurazione
        self.session = async_get_clientsession(hass)
        self.config = config

        # Inizializza i valori
        self.last_successful_update = datetime.min
        self.pun = [0.0, 0.0, 0.0, 0.0]
        self.orari = [0, 0, 0, 0]
        _LOGGER.debug("Coordinator inizializzato.")
  
    async def _async_update_data(self):
        """Aggiornamento dati a intervalli prestabiliti"""

        # Verifica che sia passato il tempo minimo dall'ultimo controllo
        if (datetime.now() - self.last_successful_update).total_seconds() < 60:
            _LOGGER.debug("Aggiornamento dati non necessario (già eseguito).")
            return
        
        # Calcola l'intervallo di date per il mese corrente
        date_today = date.today()
        date_start = date(date_today.year, date_today.month, 1)

        # URL del sito Mercato elettrico
        LOGIN_URL = 'https://www.mercatoelettrico.org/It/Tools/Accessodati.aspx?ReturnUrl=%2fIt%2fdownload%2fDownloadDati.aspx%3fval%3dMGP_Prezzi&val=MGP_Prezzi'
        DOWNLOAD_URL = 'https://www.mercatoelettrico.org/It/download/DownloadDati.aspx?val=MGP_Prezzi'
        
        # Apre la pagina per generare i cookie e i campi nascosti
        async with self.session.get(LOGIN_URL) as response:
            soup = BeautifulSoup(await response.read(), features="html.parser")
        
        # Recupera i campi nascosti __VIEWSTATE e __EVENTVALIDATION per la prossima richiesta
        viewstate = soup.find("input",{"name":"__VIEWSTATE"})['value']
        eventvalidation = soup.find("input",{"name":"__EVENTVALIDATION"})['value']
        login_payload = {
            'ctl00$ContentPlaceHolder1$CBAccetto1': 'on',
            'ctl00$ContentPlaceHolder1$CBAccetto2': 'on',
            'ctl00$ContentPlaceHolder1$Button1': 'Accetto',
            '__VIEWSTATE': viewstate,
            '__EVENTVALIDATION': eventvalidation
        }

        # Effettua il login (che se corretto porta alla pagina di download XML grazie al 'ReturnUrl')
        async with self.session.post(LOGIN_URL, data=login_payload) as response:
            soup = BeautifulSoup(await response.read(), features="html.parser")

        # Recupera i campi nascosti __VIEWSTATE per la prossima richiesta
        viewstate = soup.find("input",{"name":"__VIEWSTATE"})['value']    
        data_request_payload = {
            'ctl00$ContentPlaceHolder1$tbDataStart': date_start.strftime('%d/%m/%Y'),
            'ctl00$ContentPlaceHolder1$tbDataStop': date_today.strftime('%d/%m/%Y'),
            'ctl00$ContentPlaceHolder1$btnScarica': 'scarica+file+xml+compresso',
            '__VIEWSTATE': viewstate
        }

        # Effettua il download dello ZIP con i file XML
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
                fascia = get_fascia(dat_date, festivo, ora)

                # Calcola le statistiche
                mono.append(prezzo)
                if fascia == 3:
                    f3.append(prezzo)
                elif fascia == 2:
                    f2.append(prezzo)
                elif fascia == 1:
                    f1.append(prezzo)

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

        # Aggiorna la data dell'ultima esecuzione
        self.last_successful_update = datetime.now()
        _LOGGER.debug('Numero di dati: ' + ', '.join(str(i) for i in self.orari))
        _LOGGER.debug('Valori PUN: ' + ', '.join(str(f) for f in self.pun))
        return

def get_fascia(data, festivo, ora):
    """Restituisce il numero di fascia oraria"""
    #F1 = lu-ve 8-19
    #F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    #F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    if festivo or (data.weekday() == 6):
        # Festivi e domeniche
        return 3
    elif (data.weekday() == 5):
        # Sabato
        if (ora >= 7) and (ora < 23):
            return 2
        else:
            return 3
    else:
        # Altri giorni della settimana
        if (ora == 7) or ((ora >= 19) and (ora < 23)):
            return 2
        elif (ora == 23) or ((ora >= 0) and (ora < 7)):
            return 3
    return 1
