from homeassistant.core import HomeAssistant
from .sensor import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True
