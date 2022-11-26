from homeassistant import config_entries
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

class PUNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow per prezzi PUN"""

    # Versione della configurazione (per utilizzi futuri)
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Gestione prima configurazione da Home Assistant"""
        errors = {}
        if user_input is not None:
            # Validate user input
            if user_input[CONF_SCAN_HOUR] > 10:
                # See next section on create entry usage
                _LOGGER.info('Writing config -> ' + str(user_input))
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
