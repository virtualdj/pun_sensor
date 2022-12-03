from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from .const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_HOUR,
    CONF_ACTUAL_DATA_ONLY,
)

import logging
_LOGGER = logging.getLogger(__name__)

class PUNOptionsFlow(config_entries.OptionsFlow):
    """Opzioni per prezzi PUN"""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Inizializzazione options flow"""
        self.config_entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Gestisce le opzioni"""
        errors = {}
        if user_input is not None:
            # Validate user input
            if user_input[CONF_SCAN_HOUR] > 10:
                # See next section on create entry usage
                return self.async_create_entry(
                    title="PUN",
                    data=user_input
                )

            #errors["base"] = "auth_error"
            errors[CONF_SCAN_HOUR] = "invalid_auth"

        # Schema dati richiesti
        data_schema = {
            vol.Required(CONF_SCAN_HOUR, default=self.config_entry.data[CONF_SCAN_HOUR]): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
            vol.Optional(CONF_SCAN_INTERVAL, default=self.config_entry.data[CONF_SCAN_INTERVAL]): vol.All(cv.positive_int, vol.Range(min=10)),
            vol.Optional(CONF_ACTUAL_DATA_ONLY, default=self.config_entry.data[CONF_ACTUAL_DATA_ONLY]): cv.boolean,
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=errors
        )

    
class PUNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configurazione per prezzi PUN"""

    # Versione della configurazione (per utilizzi futuri)
    VERSION = 1

    # TODO: Non deve essere eseguita più volte!

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> PUNOptionsFlow:
        """Ottiene le opzioni per questa configurazione"""
        return PUNOptionsFlow(entry)

    async def async_step_user(self, user_input=None):
        """Gestione prima configurazione da Home Assistant"""
        errors = {}
        if user_input is not None:
            # Validate user input
            if user_input[CONF_SCAN_HOUR] > 10:
                # See next section on create entry usage
                return self.async_create_entry(
                    title="PUN",
                    data=user_input
                )

            #errors["base"] = "auth_error"
            errors[CONF_SCAN_HOUR] = "invalid_auth"

        # Schema dati richiesti
        data_schema = {
            vol.Required(CONF_SCAN_HOUR, default=1): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
            vol.Optional(CONF_SCAN_INTERVAL, default=15): vol.All(cv.positive_int, vol.Range(min=10)),
            vol.Optional(CONF_ACTUAL_DATA_ONLY, default=False): cv.boolean,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

