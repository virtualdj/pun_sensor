from enum import Enum


class PunData:
    def __init__(self) -> None:
        self.pun: dict[Fascia, list[float]] = {
            Fascia.MONO: [],
            Fascia.F1: [],
            Fascia.F2: [],
            Fascia.F3: [],
            Fascia.F23: [],
        }


class Fascia(Enum):
    MONO = "MONO"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F23 = "F23"


class PunValues:
    value: dict[Fascia, float]
    value = {
        Fascia.MONO: 0.0,
        Fascia.F1: 0.0,
        Fascia.F2: 0.0,
        Fascia.F3: 0.0,
        Fascia.F23: 0.0,
    }
