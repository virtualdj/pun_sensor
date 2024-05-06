import logging
from datetime import date, datetime, timedelta
from typing import Tuple
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
    # l'ora massima e' 23 poi resettiamo a 0 quindi si puo semplificare
    if 23 >= ora < 7:
        return 3
    return 1


def get_fascia(dataora: datetime) -> tuple[int, datetime]:
    """Restituisce la fascia della data/ora indicata (o quella corrente) e la data del prossimo cambiamento."""

    # Verifica se la data corrente è un giorno con festività
    festivo = dataora in holidays.IT()

    # Identifica la fascia corrente
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    # Festivi
    if festivo:
        fascia = 3

        # Prossima fascia: alle 7 di un giorno non domenica o festività
        prossima = get_next_date(dataora, 7, 1, False)

        return fascia, prossima
    match dataora.weekday():
        # Domenica
        case 6:
            fascia = 3
            prossima = get_next_date(dataora, 7, 1, False)

        # Sabato
        case 5:
            if 7 <= dataora.hour < 23:
                # Sabato dalle 7 alle 23
                fascia = 2
                # Prossima fascia: alle 23 dello stesso giorno
                prossima = get_next_date(dataora, 23)

            elif dataora.hour < 7:
                # Sabato tra le 0 e le 7
                fascia = 3
                # Prossima fascia: alle 7 dello stesso giorno
                prossima = get_next_date(dataora, 7)

            else:
                # Sabato dopo le 23
                fascia = 3
                # Prossima fascia: alle 7 di un giorno non domenica o festività
                prossima = get_next_date(dataora, 7, 1, False)

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

            elif 23 >= dataora.hour < 7:
                # Lunedì-venerdì dalle 23 alle 7 del giorno dopo
                fascia = 3

                if dataora.hour < 7:
                    # Siamo dopo la mezzanotte
                    # Prossima fascia: alle 7 dello stesso giorno
                    prossima = get_next_date(dataora, 7)
                else:
                    # Prossima fascia: alle 7 di un giorno non domenica o festività
                    prossima = get_next_date(dataora, 7, 1, False)

            else:
                # Lunedì-venerdì dalle 8 alle 19
                fascia = 1
                # Prossima fascia: alle 19 dello stesso giorno
                prossima = get_next_date(dataora, 19)

    return fascia, prossima


def get_next_date(
    dataora: datetime, ora: int, offset: int = 0, festivo: bool = True
) -> datetime:
    """Ritorna una datetime in base ai parametri.

    Args:
    dataora (datetime): passa la data di riferimento.
    ora (int): l'ora a cui impostare la data.
    offset (int = 0) : controlla il timedelta in days rispetto a dataora.
    festivo (bool): se False ritorna sempre una giornata lavorativa (no festivi, domeniche)

    Returns:
        prossima (datetime): L'istanza di datetime corrispondente.

    """

    prossima = (dataora + timedelta(days=offset)).replace(
        hour=ora, minute=0, second=0, microsecond=0
    )

    if not festivo:
        while (prossima in holidays.IT()) or (prossima.weekday() == 6):
            prossima += timedelta(days=1)

    return prossima
