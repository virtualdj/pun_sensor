"""Metodi di utilità generale."""

from datetime import date, datetime, timedelta, timezone
import logging
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as et  # type: ignore[import-untyped]
import holidays

from .interfaces import Fascia, PunData

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


def get_fascia(dataora: datetime) -> tuple[Fascia, datetime]:
    """Restituisce la fascia della data/ora indicata e la data del prossimo cambiamento."""

    # Verifica se la data corrente è un giorno con festività
    festivo: bool = dataora in holidays.IT()  # type: ignore[attr-defined]

    # Identifica la fascia corrente
    # F1 = lu-ve 8-19
    # F2 = lu-ve 7-8, lu-ve 19-23, sa 7-23
    # F3 = lu-sa 0-7, lu-sa 23-24, do, festivi
    # Festivi
    if festivo:
        fascia: Fascia = Fascia.F3

        # Prossima fascia: alle 7 di un giorno non domenica o festività
        prossima: datetime = get_next_date(dataora, 7, 1, True)

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

    prossima: datetime = (dataora + timedelta(days=offset)).replace(
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
        fold=dataora.fold,
        tzinfo=dataora.tzinfo,
    )


def get_ordinal_hour(dt: datetime, ref_tz: ZoneInfo = ZoneInfo("Europe/Rome")) -> int:
    """Restituisce un numero progressivo dell'ora (1-24 normalmente, 1-23 in primavera, 1-25 in autunno), contando le ore locali effettive trascorse dalla mezzanotte.

    Args:
        dt: datetime con timezone di cui restituire l'ora progressiva
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Returns:
        int: numero progressivo dell'ora nel giorno da 1 a 24 (oppure 23/25 nei giorni di cambio ora)

    Raises:
        ValueError: se dt non ha timezone

    Example:
        >>> get_ordinal_hour(datetime(2025, 10, 26, 23, 59, 0, 0, ZoneInfo("Europe/Rome")))
        25

        >>> get_ordinal_hour(datetime(2026, 3, 29, 23, 59, 0, 0, ZoneInfo("Europe/Rome")))
        23

    """
    # Controllo presenza fuso orario negli argomenti
    if dt.tzinfo is None:
        raise ValueError(
            "L'argomento dt deve essere timezone-aware (es. ZoneInfo('Europe/Rome'))."
        )

    # Calcola la mezzanotte locale
    local_midnight: datetime = datetime(dt.year, dt.month, dt.day, 0, 0, tzinfo=ref_tz)

    # Converte la mezzanotte in UTC
    start_utc: datetime = local_midnight.astimezone(timezone.utc)

    # Converte l'ora passata in UTC
    dt_utc: datetime = dt.astimezone(timezone.utc)

    # Calcola il numero di ore passate dalla mezzanotte in UTC e somma 1
    return int((dt_utc - start_utc).total_seconds() // 3600) + 1


def get_total_hours(
    dt: datetime | date, ref_tz: ZoneInfo = ZoneInfo("Europe/Rome")
) -> int:
    """Restituisce il numero totale di ore locali (24 normalmente, 23 in primavera, 25 in autunno) del giorno specificato da `dt`.

    Args:
        dt: datetime o date di cui restituire il numero massimo di ore progressive
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Returns:
        int: ore totali del giorno (23, 24 oppure 25)

    Raises:
        TypeError: se dt non è né un datetime né una date
        ValueError: se dt è un datetime senza timezone

    Example:
        >>> get_total_hours(datetime(2025, 10, 26, ZoneInfo("Europe/Rome")))
        25

        >>> get_total_hours(datetime(2026, 3, 29, ZoneInfo("Europe/Rome")))
        23

    """
    # Verifica se dt è un date
    if type(dt) is date:
        # Converte la date in datetime alle 23 per la timezone di riferimento e restituisce l'ora progressiva
        return get_ordinal_hour(
            datetime(
                year=dt.year,
                month=dt.month,
                day=dt.day,
                hour=23,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=ref_tz,
            ),
            ref_tz,
        )

    # Verifica se dt è un datetime
    if type(dt) is datetime:
        # Se è un datetime (con o senza timezone verrà verificato a valle), resetta l'orario alle 23 e restituisce l'ora progressiva
        return get_ordinal_hour(
            dt.replace(hour=23, minute=0, second=0, microsecond=0), ref_tz
        )

    # Altrimenti solleva un'eccezione
    raise TypeError("L'argomento dt deve essere datetime o date.")


def add_timedelta_via_utc(
    *,
    dt: datetime,
    delta: timedelta | None = None,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    ref_tz: ZoneInfo = ZoneInfo("Europe/Rome"),
) -> datetime:
    """Aggiunge un timedelta ad un orario considerando il calcolo in UTC.

    Args:
        dt: datetime con timezone su cui operare
        delta: timedelta da aggiungere
        days: giorni da aggiungere (se delta è None)
        hours: ore da aggiungere (se delta è None)
        minutes: minuti da aggiungere (se delta è None)
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Returns:
        datetime: orario aggiornato

    Raises:
        ValueError: se dt non ha timezone

    """
    # Controllo presenza fuso orario negli argomenti
    if dt.tzinfo is None:
        raise ValueError(
            "L'argomento dt deve essere timezone-aware (es. ZoneInfo('Europe/Rome'))."
        )

    # Controllo timedelta
    if delta is None:
        delta = timedelta(days=days, hours=hours, minutes=minutes)

    # Aggiunge il delta in UTC (per considerare anche i cambiamenti ora solare/legale)
    return (dt.astimezone(timezone.utc) + delta).astimezone(ref_tz)


def get_datetime_from_ordinal_hour(
    dt: datetime | date, ordinal_hour: int, ref_tz: ZoneInfo = ZoneInfo("Europe/Rome")
) -> datetime:
    """Restituisce il datetime corrispondente all'ora progressiva `ordinal_hour` del giorno `data`.

    Args:
        dt: datetime o date di riferimento
        ordinal_hour: l'ora progressiva del giorno `dt` da convertire (1..25)
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Raises:
        ValueError: se ordinal_hour non è compreso tra 1 e 25

    Returns:
        datetime: orario locale corrispondente all'ora progressiva specificata

    """
    if not (1 <= ordinal_hour <= 25):
        raise ValueError("ordinal_hour deve essere compreso tra 1 e 25")

    # Calcola la mezzanotte locale
    local_midnight: datetime = datetime(dt.year, dt.month, dt.day, 0, 0, tzinfo=ref_tz)

    # Converte la mezzanotte in UTC
    start_utc: datetime = local_midnight.astimezone(timezone.utc)

    # Aggiunge le ore locali effettive trascorse dalla mezzanotte
    end_utc: datetime = start_utc + timedelta(hours=ordinal_hour - 1)

    # Ritorna l'orario locale corrispondente
    return end_utc.astimezone(ref_tz)


def get_15min_datetime(dataora: datetime) -> datetime:
    """Restituisce un datetime con solo la data, l'ora e i minuti arrotondati ai 15 precedenti.

    Args:
    dataora (datetime): Data e ora di partenza.

    Returns:
        datetime: La nuova data con solo giorno, ora e minuti a step di 15.

    """
    return datetime(
        year=dataora.year,
        month=dataora.month,
        day=dataora.day,
        hour=dataora.hour,
        minute=(dataora.minute // 15) * 15,
        second=0,
        microsecond=0,
        fold=dataora.fold,
        tzinfo=dataora.tzinfo,
    )


def get_periodo_15min(dt: datetime, ref_tz: ZoneInfo = ZoneInfo("Europe/Rome")) -> int:
    """Restituisce il periodo di 15 minuti della giornata (1-96 normalmente, 1-92 in primavera, 1-100 in autunno).

    Args:
        dt: datetime con timezone di cui restituire il periodo di 15 minuti
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Returns:
        int: numero progressivo del periodo di 15 minuti (1-100)

    Raises:
        ValueError: se dt non ha timezone

    """
    # Controllo presenza fuso orario negli argomenti
    if dt.tzinfo is None:
        raise ValueError(
            "L'argomento dt deve essere timezone-aware (es. ZoneInfo('Europe/Rome'))."
        )

    # Calcola la mezzanotte locale
    local_midnight: datetime = datetime(dt.year, dt.month, dt.day, 0, 0, tzinfo=ref_tz)

    # Converte la mezzanotte in UTC
    start_utc: datetime = local_midnight.astimezone(timezone.utc)

    # Converte l'ora passata in UTC
    dt_utc: datetime = dt.astimezone(timezone.utc)

    # Calcola il numero di quarti d'ora passati dalla mezzanotte in UTC e somma 1
    return int((dt_utc - start_utc).total_seconds() // 900) + 1


def get_datetime_from_periodo_15min(
    dt: datetime | date, periodo_15min: int, ref_tz: ZoneInfo = ZoneInfo("Europe/Rome")
) -> datetime:
    """Restituisce il datetime corrispondente al periodo di 15 minuti del giorno `data`.

    Args:
        dt: datetime o date di riferimento
        periodo_15min: il numero del periodo di 15 minuti del giorno `dt` da convertire (1..100)
        ref_tz: timezone di riferimento per il calcolo (di default usa "Europe/Rome")

    Raises:
        ValueError: se periodo_15min non è compreso tra 1 e 100

    Returns:
        datetime: orario locale corrispondente all'ora progressiva specificata

    """
    if not (1 <= periodo_15min <= 100):
        raise ValueError("periodo_15min deve essere compreso tra 1 e 100")

    # Calcola la mezzanotte locale
    local_midnight: datetime = datetime(dt.year, dt.month, dt.day, 0, 0, tzinfo=ref_tz)

    # Converte la mezzanotte in UTC
    start_utc: datetime = local_midnight.astimezone(timezone.utc)

    # Aggiunge i periodi di 15 minuti effettivi trascorsi dalla mezzanotte
    end_utc: datetime = start_utc + timedelta(minutes=15 * (periodo_15min - 1))

    # Ritorna l'orario locale corrispondente
    return end_utc.astimezone(ref_tz)


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

        # Prova a cercare i prezzi orari come primo elemento
        prezzi_15min: bool = False
        primo_elemento = xml_root.find("Prezzi")
        if primo_elemento is None:
            # Prova a vedere se sono prezzi ogni 15 minuti
            prezzi_15min = True
            primo_elemento = xml_root.find("Prezzi15")
            if primo_elemento is None:
                _LOGGER.debug("Nessun prezzo supportato trovato nel file XML: %s", fn)
                continue

        # Estrae la data dal primo elemento (sarà identica per gli altri)
        dat_string: str = primo_elemento.find("Data").text  # YYYYMMDD

        # Converte la stringa giorno in data
        dat_date: date = date(
            int(dat_string[0:4]),
            int(dat_string[4:6]),
            int(dat_string[6:8]),
        )

        # Verifica la festività
        festivo: bool = dat_date in it_holidays

        # Verifica se si tratta di prezzi ogni 15 minuti
        if prezzi_15min:
            # Ottiene il numero massimo di periodi di 15 minuti per la data specificata
            max_periodi: int = 4 * get_total_hours(dat_date)

            # Considera solo oggi e domani per i prezzi ogni 15 minuti
            if dat_date >= today:
                # Estrae le rimanenti informazioni
                for prezzi in xml_root.iter("Prezzi15"):
                    # Verifica che il mercato sia corretto
                    if prezzi.find("Mercato").text != "MGP":
                        _LOGGER.warning(
                            "Mercato non supportato per i prezzi a 15 minuti nel file XML: %s.",
                            fn,
                        )
                        break

                    # Verifica che la granularità sia corretta
                    if prezzi.find("Granularity").text != "PT15":
                        _LOGGER.warning(
                            "Granularità non supportata per i prezzi a 15 minuti nel file XML: %s.",
                            fn,
                        )
                        break

                    # Estrae il periodo dall'XML
                    periodo_xml: int = int(prezzi.find("Periodo").text)

                    # Valida il periodo XML
                    # 1 .. 96 normalmente, ma anche 1..92 o 1..100 nei cambi ora
                    if not (1 <= periodo_xml <= max_periodi):
                        _LOGGER.warning(
                            "Periodo %s non valido per %s (max: %s).",
                            periodo_xml,
                            dat_string,
                            max_periodi,
                        )

                    # Converte il periodo in un datetime
                    orario_prezzo_15min: datetime = get_datetime_from_periodo_15min(
                        dat_date, periodo_xml
                    )

                    # Estrae il prezzo PUN dall'XML in un float
                    if (prezzo_xml := prezzi.find("PUN")) is not None:
                        prezzo_string_15min: str = prezzo_xml.text.replace(
                            ".", ""
                        ).replace(",", ".")
                        prezzo_15min: float = float(prezzo_string_15min) / 1000

                        # Salva il prezzo per quell'orario
                        pun_data.pun_15min[str(orario_prezzo_15min)] = prezzo_15min
                    else:
                        # PUN non valido
                        _LOGGER.warning(
                            "PUN non specificato per %s al periodo: %s.",
                            dat_string,
                            periodo_xml,
                        )

                    # Controlla che la zona del prezzo zonale sia impostata
                    if pun_data.zona is not None:
                        # Estrae il prezzo zonale dall'XML in un float
                        # basandosi sul nome dell'enum
                        if (
                            prezzo_zonale_xml := prezzi.find(pun_data.zona.name)
                        ) is not None:
                            prezzo_zonale_string_15min: str = (
                                prezzo_zonale_xml.text.replace(".", "").replace(
                                    ",", "."
                                )
                            )
                            pun_data.prezzi_zonali_15min[str(orario_prezzo_15min)] = (
                                float(prezzo_zonale_string_15min) / 1000
                            )
                        else:
                            pun_data.prezzi_zonali_15min[str(orario_prezzo_15min)] = (
                                None
                            )
        else:
            # Ottiene il numero massimo di ore per la data specificata
            max_ore: int = get_total_hours(dat_date)

            # Estrae le rimanenti informazioni
            for prezzi in xml_root.iter("Prezzi"):
                # Verifica che il mercato sia corretto
                if prezzi.find("Mercato").text != "MGP":
                    _LOGGER.warning(
                        "Mercato non supportato per i prezzi orari nel file XML: %s.",
                        fn,
                    )
                    break

                # Estrae l'ora dall'XML
                ora_xml: int = int(prezzi.find("Ora").text)

                # Valida l'orario XML
                # 1..24 normalmente, ma anche 1..23 o 1..25 nei cambi ora
                if not (1 <= ora_xml <= max_ore):
                    _LOGGER.warning(
                        "Orario %s non valido per %s (max: %s).",
                        ora_xml,
                        dat_string,
                        max_ore,
                    )

                # Converte l'ora in un datetime
                orario_prezzo: datetime = get_datetime_from_ordinal_hour(
                    dat_date, ora_xml
                )

                # Estrae il prezzo PUN dall'XML in un float
                if (prezzo_xml := prezzi.find("PUN")) is not None:
                    prezzo_string: str = prezzo_xml.text.replace(".", "").replace(
                        ",", "."
                    )
                    prezzo: float = float(prezzo_string) / 1000

                    # Per le medie mensili, considera solo i dati fino ad oggi
                    if dat_date <= today:
                        # Estrae la fascia oraria
                        fascia: Fascia = get_fascia_for_xml(
                            dat_date, festivo, orario_prezzo.hour
                        )

                        # Calcola le statistiche
                        pun_data.pun[Fascia.MONO].append(prezzo)
                        pun_data.pun[fascia].append(prezzo)

                    # Per il PUN orario, considera solo oggi e domani
                    if dat_date >= today:
                        # Salva il prezzo per quell'orario
                        pun_data.pun_orari[str(orario_prezzo)] = prezzo
                else:
                    # PUN non valido
                    _LOGGER.warning(
                        "PUN non specificato per %s ad orario: %s.", dat_string, ora_xml
                    )

                # Per i prezzi zonali, considera solo oggi e domani
                if dat_date >= today:
                    # Controlla che la zona del prezzo zonale sia impostata
                    if pun_data.zona is not None:
                        # Estrae il prezzo zonale dall'XML in un float
                        # basandosi sul nome dell'enum
                        if (
                            prezzo_zonale_xml := prezzi.find(pun_data.zona.name)
                        ) is not None:
                            prezzo_zonale_string: str = prezzo_zonale_xml.text.replace(
                                ".", ""
                            ).replace(",", ".")
                            pun_data.prezzi_zonali[str(orario_prezzo)] = (
                                float(prezzo_zonale_string) / 1000
                            )
                        else:
                            pun_data.prezzi_zonali[str(orario_prezzo)] = None

    return pun_data
