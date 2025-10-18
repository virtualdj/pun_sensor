"""Costanti utilizzate da pun_sensor."""

# Dominio HomeAssistant
DOMAIN: str = "pun_sensor"

# Tipi di sensore da creare
PUN_FASCIA_MONO: int = 0
PUN_FASCIA_F1: int = 1
PUN_FASCIA_F2: int = 2
PUN_FASCIA_F3: int = 3
PUN_FASCIA_F23: int = 4

# Intervalli di tempo per i tentativi
WEB_RETRIES_MINUTES: list[int] = [1, 10, 60, 120, 180]

# Tipi di aggiornamento
COORD_EVENT: str = "coordinator_event"
EVENT_UPDATE_FASCIA: str = "event_update_fascia"
EVENT_UPDATE_PUN: str = "event_update_pun"
EVENT_UPDATE_PREZZO_ZONALE: str = "event_update_prezzo_zonale"
EVENT_UPDATE_PREZZO_ZONALE_15MIN: str = "event_update_prezzo_zonale_15min"

# Parametri configurabili da configuration.yaml
CONF_SCAN_HOUR: str = "scan_hour"
CONF_ACTUAL_DATA_ONLY: str = "actual_data_only"
CONF_ZONA: str = "zona"

# Parametri interni
CONF_SCAN_MINUTE: str = "scan_minute"
