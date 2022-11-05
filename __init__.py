"""PUN prices integration."""
from datetime import timedelta
import logging

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up PUN prices from a config entry"""
    _LOGGER.debug("Main initialization")
    conf = config[DOMAIN]
    coordinator = PUNDataUpdateCoordinator(hass, config)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN] = {
        "conf": conf,
        "coordinator": coordinator,
    }
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True
    

class PUNDataUpdateCoordinator(DataUpdateCoordinator):
    session: ClientSession
    nane: int

    """ Gestione dell'aggiornamento da Home Assistant """
    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # Nome dei dati (a fini di log)
            name = DOMAIN,

            # Intervallo di aggiornamento
            update_interval=timedelta(seconds=10)
        )

        # Salva la sessione client
        self.session = async_get_clientsession(hass)
        self.config = config
        self.nane = 0
        _LOGGER.debug("Coordinator initialized")
   
    async def _async_update_data(self):
        _LOGGER.debug("Coordinator update requested")
        self.nane = self.nane + 1
        #async with async_timeout.timeout(10):
        #    return await self.my_api.fetch_data()
        return

