import logging
import asyncio

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from .sensor import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL = "channel"
CONF_SHORT_NUMBER = "short_number"
DEFAULT_SHORT_NUMBER = "HA"

SERVICE_OPEN_DOOR = "open_door"
SERVICE_OPEN_DOOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_CHANNEL): int,
        vol.Optional(CONF_SHORT_NUMBER,
                     default=DEFAULT_SHORT_NUMBER): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict):
    async def service_open_door(event):
        for entry in hass.data[DOMAIN]:
            entity = hass.data[DOMAIN][entry]
            if entity.entity_id == event.data[CONF_ENTITY_ID]:
                if entity.protocol is None:
                    raise HomeAssistantError("not connected")
                try:
                    return await entity.protocol.open_door(
                        event.data[CONF_CHANNEL] - 1,
                        event.data[CONF_SHORT_NUMBER])
                except asyncio.TimeoutError:
                    raise HomeAssistantError("timeout")
        else:
            raise HomeAssistantError("entity not found")

    hass.data.setdefault(DOMAIN, {})
    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_OPEN_DOOR, service_open_door,
        schema=SERVICE_OPEN_DOOR_SCHEMA
    )
    return True
