"""PUN prices integration."""
from datetime import timedelta
import logging

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
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
    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=10))
        self.hub = PUNDataHub(async_get_clientsession(hass))
        self.config = config
        _LOGGER.debug("Coordinator initialized")
   
    async def _async_update_data(self) -> list:
        _LOGGER.debug("Coordinator update requested")
        return await self.hub.list_devices()


class PUNDataHub:
    session: ClientSession
    nane: int
    retries = 0

    def __init__(self, session: ClientSession) -> None:
        _LOGGER.debug("Hub initialized")
        self.nane = 0
        self.session = session

    async def list_devices(self) -> list:
        self.nane = self.nane + 1
        _LOGGER.debug("list_devices called (" + str(self.nane) + ")")
        devs = ["A", "B", "C"]
        return devs

