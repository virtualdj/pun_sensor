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

class Fascia(Enum):
    """Enumerazione con i tipi di fascia oraria."""

    MONO = "MONO"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F23 = "F23"


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
