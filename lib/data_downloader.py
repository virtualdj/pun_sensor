from aiohttp import ClientSession, ServerConnectionError
from datetime import *
import io
from logging import Logger
from statistics import mean
import zipfile
from zoneinfo import ZoneInfo
from lib.interfaces import Fascia, PunData, PunValues
from lib.utils import extract_xml

class DataDownloader:
    session: ClientSession
    pun_values: PunValues
    pun_data: PunData
    logger: Logger

    def __init__(self, logger: Logger, session: ClientSession) -> None:
        self.logger = logger
        self.session = session
        self.pun_data = PunData()
        self.pun_values = PunValues()

    async def get(self, time_zone: ZoneInfo, actual_data_only = False):
        # Calcola l'intervallo di date per il mese corrente
        date_end = datetime.now().date()
        date_start = date(date_end.year, date_end.month, 1)

        # All'inizio del mese, aggiunge i valori del mese precedente
        # a meno che CONF_ACTUAL_DATA_ONLY non sia impostato
        if (not actual_data_only) and (date_end.day < 4):
            date_start = date_start - timedelta(days=3)

        # Aggiunge un giorno (domani) per il calcolo del prezzo zonale
        date_end += timedelta(days=1)

        # Converte le date in stringa da passare all'API Mercato elettrico
        start_date_param = date_start.strftime("%Y%m%d")
        end_date_param = date_end.strftime("%Y%m%d")

        # URL del sito Mercato elettrico
        download_url = f"https://gme.mercatoelettrico.org/DesktopModules/GmeDownload/API/ExcelDownload/downloadzipfile?DataInizio={start_date_param}&DataFine={end_date_param}&Date={end_date_param}&Mercato=MGP&Settore=Prezzi&FiltroDate=InizioFine"

        # Imposta gli header della richiesta
        heads = {
            "moduleid": "12103",
            "referer": "https://gme.mercatoelettrico.org/en-us/Home/Results/Electricity/MGP/Download?valore=Prezzi",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "tabid": "1749",
            "userid": "-1",
        }

        # Effettua il download dello ZIP con i file XML
        self.logger.debug("Inizio download file ZIP con XML.")
        async with self.session.get(download_url, headers=heads) as response:
            # Aspetta la request
            bytes_response = await response.read()

            # Se la richiesta NON e' andata a buon fine ritorna l'errore subito
            if response.status != 200:
                self.logger.error("Richiesta fallita con errore %s", response.status)
                raise ServerConnectionError(
                    f"Richiesta fallita con errore {response.status}"
                )

            # La richiesta e' andata a buon fine, tenta l'estrazione
            try:
                archive = zipfile.ZipFile(io.BytesIO(bytes_response), "r")

            # Ritorna error se l'output non è uno ZIP, o ha un errore IO
            except (zipfile.BadZipfile, OSError) as e:  # not a zip:
                self.logger.error(
                    "Download fallito con URL: %s, lunghezza %s, risposta %s",
                    download_url,
                    response.content_length,
                    response.status,
                )
                raise UpdateFailed("Archivio ZIP scaricato dal sito non valido.") from e

        # Mostra i file nell'archivio
        self.logger.debug(
            "%s file trovati nell'archivio (%s)",
            len(archive.namelist()),
            ", ".join(str(fn) for fn in archive.namelist()),
        )

        # Estrae i dati dall'archivio
        self.pun_data = extract_xml(
            archive, self.pun_data, datetime.now(time_zone).date()
        )
        archive.close()

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
        self.logger.debug(
            "Numero di dati: %s",
            ", ".join(
                str(f"{len(dati)} ({fascia.value})")
                for fascia, dati in self.pun_data.pun.items()
                if fascia != Fascia.F23
            ),
        )
        self.logger.debug(
            "Valori PUN: %s",
            ", ".join(
                f"{prezzo} ({fascia.value})"
                for fascia, prezzo in self.pun_values.value.items()
            ),
        )
