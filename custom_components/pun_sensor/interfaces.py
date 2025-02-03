"""Interfacce di gestione di pun_sensor."""

from enum import Enum


class PunData:
    """Classe che contiene i valori del PUN orario per ciascuna fascia."""

    def __init__(self) -> None:
        """Inizializza le liste di ciascuna fascia e i prezzi zonali."""

        self.pun: dict[Fascia, list[float]] = {
            Fascia.MONO: [],
            Fascia.F1: [],
            Fascia.F2: [],
            Fascia.F3: [],
            Fascia.F23: [],
        }

        self.zona: Zona | None = None
        self.prezzi_zonali: dict[str, float | None] = {}
        self.pun_orari: dict[str, float | None] = {}

class PunDataMP:
    """Classe che contiene i valori del PUN orario per ciascuna fascia."""

    def __init__(self) -> None:
        """Inizializza le liste di ciascuna fascia."""

        self.pun: dict[Fascia, list[float]] = {
            Fascia.MONO_MP: [],
            Fascia.F1_MP: [],
            Fascia.F2_MP: [],
            Fascia.F3_MP: [],
            Fascia.F23_MP: [],
        }

        self.zona: Zona | None = None
        self.prezzi_zonali: dict[str, float | None] = {}
        self.pun_orari: dict[str, float | None] = {}
        
class Fascia(Enum):
    """Enumerazione con i tipi di fascia oraria."""

    MONO = "MONO"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F23 = "F23"
    MONO_MP = "MONO_MP"
    F1_MP = "F1_MP"
    F2_MP = "F2_MP"
    F3_MP = "F3_MP"
    F23_MP = "F23_MP"


class PunValues:
    """Classe che contiene il PUN attuale di ciascuna fascia."""

    value: dict[Fascia, float]
    value = {
        Fascia.MONO: 0.0,
        Fascia.F1: 0.0,
        Fascia.F2: 0.0,
        Fascia.F3: 0.0,
        Fascia.F23: 0.0,
    }

class PunValuesMP:
    """Classe che contiene il PUN del mese precedente di ciascuna fascia."""

    value: dict[Fascia, float]
    value = {
        Fascia.MONO_MP: 0.0,
        Fascia.F1_MP: 0.0,
        Fascia.F2_MP: 0.0,
        Fascia.F3_MP: 0.0,
        Fascia.F23_MP: 0.0,
    }

class Zona(Enum):
    """Enumerazione con i nomi delle zone per i prezzi zonali."""

    AUST = "Austria"
    XAUS = "Austria Coupling"
    CALA = "Calabria"
    CNOR = "Centro Nord"
    CSUD = "Centro Sud"
    CORS = "Corsica"
    COAC = "Corsica AC"
    FRAN = "Francia"
    XFRA = "Francia Coupling"
    GREC = "Grecia"
    XGRE = "Grecia Coupling"
    NAT = "Italia"
    COUP = "Italia Coupling"
    MALT = "Malta"
    MONT = "Montenegro"
    NORD = "Nord"
    SARD = "Sardegna"
    SICI = "Sicilia"
    SLOV = "Slovenia"
    BSP = "Slovenia Coupling"
    SUD = "Sud"
    SVIZ = "Svizzera"


# Zona predefinita
DEFAULT_ZONA = Zona.NAT
