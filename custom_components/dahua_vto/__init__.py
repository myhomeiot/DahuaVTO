import logging
import asyncio

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import CONF_ENTITY_ID, CONF_TIMEOUT, CONF_EVENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from .sensor import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL = "channel"
CONF_SHORT_NUMBER = "short_number"
CONF_METHOD = "method"
CONF_PARAMS = "params"
CONF_TAG = "tag"

DEFAULT_TIMEOUT = 5

SERVICE_OPEN_DOOR = "open_door"
SERVICE_OPEN_DOOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_CHANNEL): int,
        vol.Optional(CONF_SHORT_NUMBER, default="HA"): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
    }
)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_METHOD): object,
        vol.Optional(CONF_PARAMS, default=None): object,
        vol.Optional(CONF_EVENT, default=True): bool,
        vol.Optional(CONF_TAG, default=None): object,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
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
                        event.data[CONF_SHORT_NUMBER],
                        event.data[CONF_TIMEOUT])
                except asyncio.TimeoutError:
                    raise HomeAssistantError("timeout")
        else:
            raise HomeAssistantError("entity not found")

    async def service_send_command(event):
        for entry in hass.data[DOMAIN]:
            entity = hass.data[DOMAIN][entry]
            if entity.entity_id == event.data[CONF_ENTITY_ID]:
                if entity.protocol is None:
                    raise HomeAssistantError("not connected")
                try:
                    return await entity.protocol.send_command(
                        event.data[CONF_METHOD],
                        event.data[CONF_PARAMS],
                        event.data[CONF_EVENT],
                        event.data[CONF_TAG],
                        event.data[CONF_TIMEOUT])
                except asyncio.TimeoutError:
                    raise HomeAssistantError("timeout")
        else:
            raise HomeAssistantError("entity not found")

    hass.data.setdefault(DOMAIN, {})
    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_OPEN_DOOR, service_open_door,
        schema=SERVICE_OPEN_DOOR_SCHEMA
    )
    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_SEND_COMMAND, service_send_command,
        schema=SERVICE_SEND_COMMAND_SCHEMA
    )
    return True
