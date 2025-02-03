"""Metodi di utilità generale."""

from datetime import date, datetime, timedelta
import logging
from zipfile import ZipFile

import defusedxml.ElementTree as et  # type: ignore[import-untyped]
import holidays

from .interfaces import Fascia, PunData, PunDataMP

# Ottiene il logger
_LOGGER = logging.getLogger(__name__)


def get_fascia_for_xml(data: date, festivo: bool, ora: int) -> Fascia:
    """Restituisce la fascia oraria di un determinato giorno/ora."""
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi

    # Festivi e domeniche
    if festivo or (data.weekday() == 6):
        return Fascia.F3

    # Sabato
    if data.weekday() == 5:
        if 7 <= ora < 23:
            return Fascia.F2
        return Fascia.F3

    # Altri giorni della settimana
    if ora == 7 or 19 <= ora < 23:
        return Fascia.F2
    if 8 <= ora < 19:
        return Fascia.F1
    return Fascia.F3

def get_fascia_for_xml2(data: date, festivo: bool, ora: int) -> Fascia:
    """Restituisce la fascia oraria di un determinato giorno/ora."""
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi

    # Festivi e domeniche
    if festivo or (data.weekday() == 6):
        return Fascia.F3_MP

    # Sabato
    if data.weekday() == 5:
        if 7 <= ora < 23:
            return Fascia.F2_MP
        return Fascia.F3_MP

    # Altri giorni della settimana
    if ora == 7 or 19 <= ora < 23:
        return Fascia.F2_MP
    if 8 <= ora < 19:
        return Fascia.F1_MP
    return Fascia.F3_MP

def get_fascia(dataora: datetime) -> tuple[Fascia, datetime]:
    """Restituisce la fascia della data/ora indicata e la data del prossimo cambiamento."""

    # Verifica se la data corrente è un giorno con festività
    festivo = dataora in holidays.IT()  # type: ignore[attr-defined]

    # Identifica la fascia corrente
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    # Festivi
    if festivo:
        fascia = Fascia.F3

        # Prossima fascia: alle 7 di un giorno non domenica o festività
        prossima = get_next_date(dataora, 7, 1, True)

        return fascia, prossima
    match dataora.weekday():
        # Domenica
        case 6:
            fascia = Fascia.F3
            prossima = get_next_date(dataora, 7, 1, True)

        # Sabato
        case 5:
            if 7 <= dataora.hour < 23:
                # Sabato dalle 7 alle 23
                fascia = Fascia.F2
                # Prossima fascia: alle 23 dello stesso giorno
                prossima = get_next_date(dataora, 23)
            # abbiamo solo due fasce quindi facciamo solo il check per la prossima fascia
            else:
                # Sabato dopo le 23 e prima delle 7
                fascia = Fascia.F3

                if dataora.hour < 7:
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, True)

        # Altri giorni della settimana
        case _:
            if dataora.hour == 7 or 19 <= dataora.hour < 23:
                # Lunedì-venerdì dalle 7 alle 8 e dalle 19 alle 23
                fascia = Fascia.F2

                if dataora.hour == 7:
                    # Prossima fascia: alle 8 dello stesso giorno
                    prossima = get_next_date(dataora, 8)
                else:
                    # Prossima fascia: alle 23 dello stesso giorno
                    prossima = get_next_date(dataora, 23)

            elif 8 <= dataora.hour < 19:
                # Lunedì-venerdì dalle 8 alle 19
                fascia = Fascia.F1
                # Prossima fascia: alle 19 dello stesso giorno
                prossima = get_next_date(dataora, 19)

            else:
                # Lunedì-venerdì dalle 23 alle 7 del giorno dopo
                fascia = Fascia.F3

                if dataora.hour < 7:
                    # Siamo dopo la mezzanotte
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, True)

    return fascia, prossima


def get_next_date(
    dataora: datetime, ora: int, offset: int = 0, feriale: bool = False, minuto: int = 0
) -> datetime:
    """Ritorna una datetime in base ai parametri.

    Args:
    dataora (datetime): passa la data di riferimento.
    ora (int): l'ora a cui impostare la data.
    offset (int = 0): scostamento in giorni rispetto a dataora.
    feriale (bool = False): se True ritorna sempre una giornata lavorativa (no festivi, domeniche)
    minuto (int = 0): minuto a cui impostare la data.

    Returns:
        prossima (datetime): L'istanza di datetime corrispondente.

    """

    prossima = (dataora + timedelta(days=offset)).replace(
        hour=ora, minute=minuto, second=0, microsecond=0
    )

    if feriale:
        while (prossima in holidays.IT()) or (prossima.weekday() == 6):  # type: ignore[attr-defined]
            prossima += timedelta(days=1)

    return prossima


def get_hour_datetime(dataora: datetime) -> datetime:
    """Restituisce un datetime con solo la data e l'ora.

    Args:
    dataora (datetime): Data e ora di partenza.

    Returns:
        datetime: La nuova data con solo giorno e ora.

    """
    return datetime(
        year=dataora.year,
        month=dataora.month,
        day=dataora.day,
        hour=dataora.hour,
        minute=0,
        second=0,
        microsecond=0,
    )


def datetime_to_packed_string(dataora: datetime) -> str:
    """Restituisce una stringa usabile come chiave dizionario a partire da un datime.

    Args:
    dataora (datetime): Data e ora di partenza.

    Returns:
        str: Stringa in formato YYYYMMDDHH.

    """
    return dataora.strftime("%Y%m%d%H")


def extract_xml(archive: ZipFile, pun_data: PunData, today: date) -> PunData:
    """Estrae i valori del pun per ogni fascia da un archivio zip contenente un XML.

    Args:
    archive (ZipFile): archivio ZIP con i file XML all'interno.
    pun_data (PunData): riferimento alla struttura che verrà modificata con i dati da XML.
    today (date): data di oggi, utilizzata per memorizzare il prezzo zonale.

    Returns:
    List[ list[MONO: float], list[F1: float], list[F2: float], list[F3: float] ]

    """
    # Carica le festività
    it_holidays = holidays.IT()  # type: ignore[attr-defined]

    # Azzera i dati precedenti
    for fascia_da_svuotare in pun_data.pun.values():
        fascia_da_svuotare.clear()

    # Esamina ogni file XML nello ZIP (ordinandoli prima)
    for fn in sorted(archive.namelist()):
        # Scompatta il file XML in memoria
        xml_tree = et.parse(archive.open(fn))

        # Parsing dell'XML (1 file = 1 giorno)
        xml_root = xml_tree.getroot()

        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string = xml_root.find("Prezzi").find("Data").text  # YYYYMMDD

        # Converte la stringa giorno in data
        dat_date = date(
            int(dat_string[0:4]),
            int(dat_string[4:6]),
            int(dat_string[6:8]),
        )

        # Verifica la festività
        festivo = dat_date in it_holidays

        # Estrae le rimanenti informazioni
        for prezzi in xml_root.iter("Prezzi"):
            # Estrae l'ora dall'XML
            ora = int(prezzi.find("Ora").text) - 1  # 1..24

            # Estrae il prezzo PUN dall'XML in un float
            if (prezzo_xml := prezzi.find("PUN")) is not None:
                prezzo_string = prezzo_xml.text.replace(".", "").replace(",", ".")
                prezzo = float(prezzo_string) / 1000

                # Per le medie mensili, considera solo i dati fino ad oggi
                if dat_date <= today:
                    # Estrae la fascia oraria
                    fascia = get_fascia_for_xml(dat_date, festivo, ora)

                    # Calcola le statistiche
                    pun_data.pun[Fascia.MONO].append(prezzo)
                    pun_data.pun[fascia].append(prezzo)

                # Per il PUN orario, considera solo oggi e domani
                if dat_date >= today:
                    # Compone l'orario
                    orario_prezzo = datetime_to_packed_string(
                        datetime(
                            year=dat_date.year,
                            month=dat_date.month,
                            day=dat_date.day,
                            hour=ora,
                            minute=0,
                            second=0,
                            microsecond=0,
                        )
                    )
                    # E salva il prezzo per quell'orario
                    pun_data.pun_orari[orario_prezzo] = prezzo
            else:
                # PUN non valido
                _LOGGER.warning(
                    "PUN non specificato per %s ad orario: %s.", dat_string, ora
                )

            # Per i prezzi zonali, considera solo oggi e domani
            if dat_date >= today:
                # Compone l'orario
                orario_prezzo = datetime_to_packed_string(
                    datetime(
                        year=dat_date.year,
                        month=dat_date.month,
                        day=dat_date.day,
                        hour=ora,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                )

                # Controlla che la zona del prezzo zonale sia impostata
                if pun_data.zona is not None:
                    # Estrae il prezzo zonale dall'XML in un float
                    # basandosi sul nome dell'enum
                    if (
                        prezzo_zonale_xml := prezzi.find(pun_data.zona.name)
                    ) is not None:
                        prezzo_zonale_string = prezzo_zonale_xml.text.replace(
                            ".", ""
                        ).replace(",", ".")
                        pun_data.prezzi_zonali[orario_prezzo] = (
                            float(prezzo_zonale_string) / 1000
                        )
                    else:
                        pun_data.prezzi_zonali[orario_prezzo] = None

    return pun_data

def extract_xml2(archive: ZipFile, pun_data: PunDataMP, today: date) -> PunDataMP:
    """Estrae i valori del pun per ogni fascia da un archivio zip contenente un XML.

    Args:
    archive (ZipFile): archivio ZIP con i file XML all'interno.
    pun_data (PunData): riferimento alla struttura che verrà modificata con i dati da XML.
    today (date): data di oggi, utilizzata per memorizzare il prezzo zonale.

    Returns:
    List[ list[MONO: float], list[F1: float], list[F2: float], list[F3: float] ]

    """
    # Carica le festività
    it_holidays = holidays.IT()  # type: ignore[attr-defined]

    # Azzera i dati precedenti
    for fascia_da_svuotare in pun_data.pun.values():
        fascia_da_svuotare.clear()

    # Esamina ogni file XML nello ZIP (ordinandoli prima)
    for fn in sorted(archive.namelist()):
        # Scompatta il file XML in memoria
        xml_tree = et.parse(archive.open(fn))

        # Parsing dell'XML (1 file = 1 giorno)
        xml_root = xml_tree.getroot()

        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string = xml_root.find("Prezzi").find("Data").text  # YYYYMMDD

        # Converte la stringa giorno in data
        dat_date = date(
            int(dat_string[0:4]),
            int(dat_string[4:6]),
            int(dat_string[6:8]),
        )

        # Verifica la festività
        festivo = dat_date in it_holidays

        # Estrae le rimanenti informazioni
        for prezzi in xml_root.iter("Prezzi"):
            # Estrae l'ora dall'XML
            ora = int(prezzi.find("Ora").text) - 1  # 1..24

            # Estrae il prezzo PUN dall'XML in un float
            if (prezzo_xml := prezzi.find("PUN")) is not None:
                prezzo_string = prezzo_xml.text.replace(".", "").replace(",", ".")
                prezzo = float(prezzo_string) / 1000

                # Per le medie mensili, considera solo i dati fino ad oggi
                if dat_date <= today:
                    # Estrae la fascia oraria
                    fascia = get_fascia_for_xml2(dat_date, festivo, ora)

                    # Calcola le statistiche
                    pun_data.pun[Fascia.MONO_MP].append(prezzo)
                    pun_data.pun[fascia].append(prezzo)

                # Per il PUN orario, considera solo oggi e domani
                if dat_date >= today:
                    # Compone l'orario
                    orario_prezzo = datetime_to_packed_string(
                        datetime(
                            year=dat_date.year,
                            month=dat_date.month,
                            day=dat_date.day,
                            hour=ora,
                            minute=0,
                            second=0,
                            microsecond=0,
                        )
                    )
                    # E salva il prezzo per quell'orario
                    pun_data.pun_orari[orario_prezzo] = prezzo
            else:
                # PUN non valido
                _LOGGER.warning(
                    "PUN non specificato per %s ad orario: %s.", dat_string, ora
                )

            # Per i prezzi zonali, considera solo oggi e domani
            if dat_date >= today:
                # Compone l'orario
                orario_prezzo = datetime_to_packed_string(
                    datetime(
                        year=dat_date.year,
                        month=dat_date.month,
                        day=dat_date.day,
                        hour=ora,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                )

                # Controlla che la zona del prezzo zonale sia impostata
                if pun_data.zona is not None:
                    # Estrae il prezzo zonale dall'XML in un float
                    # basandosi sul nome dell'enum
                    if (
                        prezzo_zonale_xml := prezzi.find(pun_data.zona.name)
                    ) is not None:
                        prezzo_zonale_string = prezzo_zonale_xml.text.replace(
                            ".", ""
                        ).replace(",", ".")
                        pun_data.prezzi_zonali[orario_prezzo] = (
                            float(prezzo_zonale_string) / 1000
                        )
                    else:
                        pun_data.prezzi_zonali[orario_prezzo] = None

    return pun_data
