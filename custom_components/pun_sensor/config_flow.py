"""UI di configurazione per pun_sensor."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import CONF_ACTUAL_DATA_ONLY, CONF_SCAN_HOUR, CONF_ZONA, DOMAIN
from .interfaces import DEFAULT_ZONA, Zona


class PUNOptionsFlow(config_entries.OptionsFlow):
    """Opzioni per prezzi PUN (= riconfigurazione successiva)."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Inizializzazione opzioni."""
        self.config_entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Gestisce le opzioni di configurazione."""
        errors: dict[str, str] | None = {}
        if user_input is not None:
            # Configurazione valida (validazione integrata nello schema)
            return self.async_create_entry(title="PUN", data=user_input)

        # Schema dati di opzione (con default sui valori attuali)
        data_schema = {
            vol.Required(
                CONF_ZONA,
                default=self.config_entry.options.get(
                    CONF_ZONA, self.config_entry.data[CONF_ZONA]
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=zona.name, label=zona.value)
                        for zona in Zona
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="zona",
                    sort=False,
                ),
            ),
            vol.Required(
                CONF_SCAN_HOUR,
                default=self.config_entry.options.get(
                    CONF_SCAN_HOUR, self.config_entry.data[CONF_SCAN_HOUR]
                ),
            ): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
            vol.Optional(
                CONF_ACTUAL_DATA_ONLY,
                default=self.config_entry.options.get(
                    CONF_ACTUAL_DATA_ONLY, self.config_entry.data[CONF_ACTUAL_DATA_ONLY]
                ),
            ): cv.boolean,
        }

        # Mostra la schermata di configurazione, con gli eventuali errori
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=errors
        )


class PUNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configurazione per prezzi PUN (= prima configurazione)."""

    # Versione della configurazione
    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PUNOptionsFlow:
        """Ottiene le opzioni per questa configurazione."""
        return PUNOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Gestione prima configurazione da Home Assistant."""
        # Controlla che l'integrazione non venga eseguita più volte
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = {}
        if user_input is not None:
            # Configurazione valida (validazione integrata nello schema)
            return self.async_create_entry(title="PUN", data=user_input)

        # Schema dati di configurazione (con default fissi)
        data_schema = {
            vol.Required(CONF_ZONA, default=DEFAULT_ZONA.name): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=zona.name, label=zona.value)
                        for zona in Zona
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="zona",
                    sort=False,
                ),
            ),
            vol.Required(CONF_SCAN_HOUR, default=1): vol.All(
                cv.positive_int, vol.Range(min=0, max=23)
            ),
            vol.Optional(CONF_ACTUAL_DATA_ONLY, default=False): cv.boolean,
        }

        # Mostra la schermata di configurazione, con gli eventuali errori
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )
