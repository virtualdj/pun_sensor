"""Costanti utilizzate da pun_sensor."""

# Dominio HomeAssistant
DOMAIN = "pun_sensor"

# Tipi di sensore da creare
PUN_FASCIA_MONO = 0
PUN_FASCIA_F1 = 1
PUN_FASCIA_F2 = 2
PUN_FASCIA_F3 = 3
PUN_FASCIA_F23 = 4

# Intervalli di tempo per i tentativi
WEB_RETRIES_MINUTES = [1, 10, 60, 120, 180]

# Tipi di aggiornamento
COORD_EVENT = "coordinator_event"
EVENT_UPDATE_FASCIA = "event_update_fascia"
EVENT_UPDATE_PUN = "event_update_pun"
EVENT_UPDATE_PREZZO_ZONALE = "event_update_prezzo_zonale"

# Parametri configurabili da configuration.yaml
CONF_SCAN_HOUR = "scan_hour"
CONF_ACTUAL_DATA_ONLY = "actual_data_only"

# Parametri interni
CONF_SCAN_MINUTE = "scan_minute"
