"""utils"""

# pylint: disable= E1101
import logging
from datetime import date, datetime, timedelta
from zipfile import ZipFile

import defusedxml.ElementTree as et
import holidays

_LOGGER = logging.getLogger(__name__)


def get_fascia_for_xml(data: date, festivo: bool, ora: int) -> int:
    """Restituisce il numero di fascia oraria di un determinato giorno/ora"""
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi

    # Festivi e domeniche
    if festivo or (data.weekday() == 6):
        return 3

    # Sabato
    if data.weekday() == 5:
        if 7 <= ora < 23:
            return 2
        return 3

    # Altri giorni della settimana
    if ora == 7 or 19 <= ora < 23:
        return 2
    if 8 <= ora < 19:
        return 1
    return 3


def get_fascia(dataora: datetime) -> tuple[int, datetime]:
    """Restituisce la fascia della data/ora indicata (o quella corrente) e la data del prossimo cambiamento."""

    # Verifica se la data corrente è un giorno con festività
    festivo = dataora in holidays.IT()  # type: ignore

    # Identifica la fascia corrente
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    # Festivi
    if festivo:
        fascia = 3

        # Prossima fascia: alle 7 di un giorno non domenica o festività
        prossima = get_next_date(dataora, 7, 1, True)

        return fascia, prossima
    match dataora.weekday():
        # Domenica
        case 6:
            fascia = 3
            prossima = get_next_date(dataora, 7, 1, True)

        # Sabato
        case 5:
            if 7 <= dataora.hour < 23:
                # Sabato dalle 7 alle 23
                fascia = 2
                # Prossima fascia: alle 23 dello stesso giorno
                prossima = get_next_date(dataora, 23)
            # abbiamo solo due fasce quindi facciamo solo il check per la prossima fascia
            else:
                # Sabato dopo le 23 e prima delle 7
                fascia = 3

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
                fascia = 2

                if dataora.hour == 7:
                    # Prossima fascia: alle 8 dello stesso giorno
                    prossima = get_next_date(dataora, 8)
                else:
                    # Prossima fascia: alle 23 dello stesso giorno
                    prossima = get_next_date(dataora, 23)

            elif 8 <= dataora.hour < 19:
                # Lunedì-venerdì dalle 8 alle 19
                fascia = 1
                # Prossima fascia: alle 19 dello stesso giorno
                prossima = get_next_date(dataora, 19)

            else:
                # Lunedì-venerdì dalle 23 alle 7 del giorno dopo
                fascia = 3

                if dataora.hour < 7:
                    # Siamo dopo la mezzanotte
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, True)

    return fascia, prossima


def get_next_date(
    dataora: datetime, ora: int, offset: int = 0, feriale: bool = False
) -> datetime:
    """Ritorna una datetime in base ai parametri.

    Args:
    dataora (datetime): passa la data di riferimento.
    ora (int): l'ora a cui impostare la data.
    offset (int = 0) : controlla il timedelta in days rispetto a dataora.
    feriale (bool = False): se True ritorna sempre una giornata lavorativa (no festivi, domeniche)

    Returns:
        prossima (datetime): L'istanza di datetime corrispondente.

    """

    prossima = (dataora + timedelta(days=offset)).replace(
        hour=ora, minute=0, second=0, microsecond=0
    )

    if feriale:
        while (prossima in holidays.IT()) or (prossima.weekday() == 6):  # type: ignore
            prossima += timedelta(days=1)

    return prossima


def extract_xml(archive: ZipFile):
    """Estrae i valori del pun per ogni fascia da un archivio zip contenente un XML.

    Returns:
    List[ list[MONO: float], list[F1: float], list[F2: float], list[F3: float] ]
    """
    # Carica le festività
    it_holidays = holidays.IT()  # type: ignore

    # Esamina ogni file XML nello ZIP (ordinandoli prima)
    for fn in sorted(archive.namelist()):
        # Scompatta il file XML in memoria
        xml_tree = et.parse(archive.open(fn))

        # Parsing dell'XML (1 file = 1 giorno)
        xml_root = xml_tree.getroot()

        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string = (
            xml_root.find("Prezzi").find("Data").text  # type: ignore
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

    return [mono, f1, f2, f3]
