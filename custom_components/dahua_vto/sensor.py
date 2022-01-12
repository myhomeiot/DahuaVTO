"""Platform for sensor integration."""
import json
import struct
import asyncio
import hashlib
import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_HOST, \
    CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, CONF_EVENT
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "dahua_vto"
DAHUA_PROTO_DHIP = 0x5049484400000020
DAHUA_HEADER_FORMAT = "<QLLQQ"
DAHUA_REALM_DHIP = 268632079  # DHIP REALM Login Challenge
DAHUA_LOGIN_PARAMS = {
    "clientType": "", "ipAddr": "(null)", "loginType": "Direct"}

DEFAULT_KEEPALIVEINTERVAL = 60

_LOGGER = logging.getLogger(__name__)

# Validation of the platform configuration
DEFAULT_NAME = "Dahua VTO"
DEFAULT_PORT = 5000
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


# Validation of the services
CONF_CHANNEL = "channel"
CONF_SHORT_NUMBER = "short_number"
CONF_METHOD = "method"
CONF_INSTANCE_PARAMS = "instance_params"
CONF_PARAMS = "params"
CONF_TAG = "tag"

SERVICE_DEFAULT_TIMEOUT = 5

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_METHOD): object,
        vol.Optional(CONF_PARAMS, default=None): object,
        vol.Optional(CONF_EVENT, default=True): bool,
        vol.Optional(CONF_TAG, default=None): object,
        vol.Optional(CONF_TIMEOUT, default=SERVICE_DEFAULT_TIMEOUT): int,
    }
)

SERVICE_SEND_INSTANCE_COMMAND = "send_instance_command"
SERVICE_SEND_INSTANCE_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_METHOD): object,
        vol.Optional(CONF_INSTANCE_PARAMS, default=None): object,
        vol.Optional(CONF_PARAMS, default=None): object,
        vol.Optional(CONF_EVENT, default=True): bool,
        vol.Optional(CONF_TAG, default=None): object,
        vol.Optional(CONF_TIMEOUT, default=SERVICE_DEFAULT_TIMEOUT): int,
    }
)

SERVICE_OPEN_DOOR = "open_door"
SERVICE_OPEN_DOOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.string,
        vol.Required(CONF_CHANNEL): int,
        vol.Optional(CONF_SHORT_NUMBER, default="HA"): cv.string,
        vol.Optional(CONF_TIMEOUT, default=SERVICE_DEFAULT_TIMEOUT): int,
    }
)


async def async_setup_platform(
        hass, config, add_entities, discovery_info=None
):
    """Set up the sensor platform."""
    name = config[CONF_NAME]
    entity = DahuaVTO(hass, name, config)
    hass.data[DOMAIN][name] = entity
    add_entities([entity])
    hass.loop.create_task(entity.async_run())

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        SERVICE_SEND_COMMAND_SCHEMA,
        "async_send_command"
    )
    platform.async_register_entity_service(
        SERVICE_SEND_INSTANCE_COMMAND,
        SERVICE_SEND_INSTANCE_COMMAND_SCHEMA,
        "async_send_instance_command"
    )
    platform.async_register_entity_service(
        SERVICE_OPEN_DOOR,
        SERVICE_OPEN_DOOR_SCHEMA,
        "async_open_door"
    )
    return True


class DahuaVTOClient(asyncio.Protocol):

    def __init__(self, hass, entity, username, password, on_connection_lost):
        self.entity = entity
        self.hass = hass
        self.username = username
        self.password = password
        self.loop = asyncio.get_running_loop()
        self.on_connection_lost = on_connection_lost

        self.request_id = 0
        self.sessionId = 0
        self.chunk = b''
        self.header_len = struct.calcsize(DAHUA_HEADER_FORMAT)
        self.keepAliveInterval = None
        self.transport = None
        self.heartbeat = None
        self.on_response_id = None
        self.on_response = None
        self.attrs = None

    def connection_made(self, transport):
        self.transport = transport
        self.send({"method": "global.login", "params": DAHUA_LOGIN_PARAMS})

    def connection_lost(self, exc):
        if self.heartbeat is not None:
            self.heartbeat.cancel()
            self.heartbeat = None
        if not self.on_connection_lost.cancelled():
            self.on_connection_lost.set_result(True)

    def hashed_password(self, random, realm):
        h = hashlib.md5(f"{self.username}:{realm}:{self.password}".encode(
            "utf-8")).hexdigest().upper()
        return hashlib.md5(f"{self.username}:{random}:{h}".encode(
            "utf-8")).hexdigest().upper()

    def receive(self, message):
        params = message.get("params")
        error = message.get("error")

        if error is not None:
            if error["code"] == DAHUA_REALM_DHIP:
                self.sessionId = message["session"]
                login = DAHUA_LOGIN_PARAMS
                login["userName"] = self.username
                login["password"] = self.hashed_password(
                    params["random"], params["realm"])
                self.send({"method": "global.login", "params": login})
            else:
                raise Exception("{}: {}".format(
                    error.get("code"), error.get("message")))
        elif message["id"] == 2:
            self.keepAliveInterval = None if params is None \
                else params.get("keepAliveInterval")
            if self.keepAliveInterval is None:
                self.keepAliveInterval = DEFAULT_KEEPALIVEINTERVAL
                _LOGGER.debug(f"Using default keepAliveInterval "
                              f"({self.keepAliveInterval})")
            if self.heartbeat is not None:
                raise Exception("Heartbeat already run")
            self.heartbeat = self.loop.create_task(self.heartbeat_loop())
            self.send({"method": "eventManager.attach",
                       "params": {"codes": ["All"]}})
            self.send({"method": "configManager.attach",
                       "params": {"name": "CommGlobal"}})
        elif message.get("method") == "client.notifyEventStream":
            for event in params.get("eventList"):
                event["entity_id"] = self.entity.entity_id
                self.hass.bus.fire(DOMAIN, event)
        elif message.get("method") == "client.notifyConfigChange":
            table = params.get("table")
            table["entity_id"] = self.entity.entity_id
            table["Code"] = message.get("method")
            self.hass.bus.fire(DOMAIN, table)

    def data_received(self, data):
        try:
            self.chunk += data
            while len(self.chunk) > 0:
                if len(self.chunk) < self.header_len:
                    break
                packet_proto, *_, packet_len = struct.unpack_from(
                    DAHUA_HEADER_FORMAT, self.chunk)
                if packet_proto != DAHUA_PROTO_DHIP:
                    raise Exception("Wrong proto")
                tail = self.header_len + packet_len
                if tail > len(self.chunk):
                    break
                packet = self.chunk[self.header_len:tail].decode(
                    "utf-8", "ignore")
                self.chunk = self.chunk[tail:]

                _LOGGER.debug("<<< {}".format(packet.rstrip()))
                message = json.loads(packet)

                if self.on_response is not None \
                        and self.on_response_id == message["id"]:
                    self.on_response.set_result(message)
                else:
                    self.receive(message)
        except Exception as e:
            self.on_connection_lost.set_exception(e)

    def send(self, message):
        self.request_id += 1
        # Removed: "magic": DAHUA_MAGIC ("0x1234")
        message["id"] = self.request_id
        message["session"] = self.sessionId
        data = json.dumps(message, separators=(',', ':'))
        _LOGGER.debug(f">>> {data}")
        self.transport.write(
            struct.pack(DAHUA_HEADER_FORMAT, DAHUA_PROTO_DHIP,
                        self.sessionId, self.request_id, len(data), len(data))
            + data.encode("utf-8", "ignore"))
        return self.request_id

    async def command(self, message, timeout=5):
        self.on_response = self.loop.create_future()
        self.on_response_id = self.send(message)
        try:
            return await asyncio.wait_for(self.on_response, timeout=timeout)
        finally:
            self.on_response = self.on_response_id = None

    async def send_command(self, method, params, event, tag, timeout):
        if isinstance(method, dict):
            message = method
        else:
            message = {"method": method}
        if params:
            message["params"] = params
        result = await self.command(message, timeout)
        if event:
            del result["id"]
            del result["session"]
            result["method"] = method
            if tag:
                result["tag"] = tag
            result["entity_id"] = self.entity.entity_id
            self.hass.bus.fire(DOMAIN, result)

    async def send_instance_command(
            self, method, instance_params, params, event, tag, timeout
    ):
        service = method.partition('.')[0]
        object_id = (await self.command({
            "method": f"{service}.factory.instance",
            "params": instance_params}, timeout))["result"]
        if object_id:
            try:
                result = await self.command({
                    "method": method, "object": object_id, "params": params})
                if event:
                    del result["id"]
                    del result["session"]
                    result["method"] = method
                    if tag:
                        result["tag"] = tag
                    result["entity_id"] = self.entity.entity_id
                    self.hass.bus.fire(DOMAIN, result)
            finally:
                await self.command({
                    "method": f"{service}.destroy", "object": object_id})

    async def heartbeat_loop(self):
        result = await self.command({"method": "magicBox.getSystemInfo"})
        if result.get("result"):
            params = result.get("params")
            self.attrs = {"deviceType": params.get("deviceType"),
                          "serialNumber": params.get("serialNumber")}
        while True:
            try:
                await asyncio.sleep(self.keepAliveInterval)
                await self.command({
                    "method": "global.keepAlive",
                    "params": {"timeout": self.keepAliveInterval,
                               "action": True}})
            except asyncio.CancelledError:
                raise
            except Exception:
                break
        transport = self.transport
        self.transport = None
        transport.close()


class DahuaVTO(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, name, config):
        """Initialize the sensor."""
        self.hass = hass
        self.config = config

        self._name = name
        self._state = None
        self.protocol = None

    async def async_run(self):
        while True:
            try:
                _LOGGER.debug("Connecting {}:{}, username {}".format(
                    self.config[CONF_HOST], self.config[CONF_PORT],
                    self.config[CONF_USERNAME]))
                on_connection_lost = self.hass.loop.create_future()
                t, self.protocol = await self.hass.loop.create_connection(
                    lambda: DahuaVTOClient(
                        self.hass, self, self.config[CONF_USERNAME],
                        self.config[CONF_PASSWORD], on_connection_lost),
                    self.config[CONF_HOST], self.config[CONF_PORT])
                try:
                    await on_connection_lost
                    raise Exception("Connection closed")
                finally:
                    self.protocol = None
                    t.close()
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _LOGGER.error("{}: {}, retry in {} seconds".format(
                    self.name, e, self.config[CONF_TIMEOUT]))
                await asyncio.sleep(self.config[CONF_TIMEOUT])

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def available(self):
        return self._state is not None

    @property
    def state_attributes(self):
        return self.protocol.attrs if self.protocol else None

    def update(self):
        self._state = 'OK' if self.protocol is not None else None

    async def async_send_command(
            self, method, params, event, tag, timeout
    ) -> None:
        if self.protocol is None:
            raise HomeAssistantError("not connected")
        try:
            await self.protocol.send_command(
                method, params, event, tag, timeout
            )
        except asyncio.TimeoutError:
            raise HomeAssistantError("timeout")

    async def async_send_instance_command(
            self, method, instance_params, params, event, tag, timeout
    ) -> None:
        if self.protocol is None:
            raise HomeAssistantError("not connected")
        try:
            await self.protocol.send_instance_command(
                method, instance_params, params, event, tag, timeout
            )
        except asyncio.TimeoutError:
            raise HomeAssistantError("timeout")

    async def async_open_door(self, channel, short_number, timeout) -> None:
        if self.protocol is None:
            raise HomeAssistantError("not connected")
        try:
            await self.protocol.send_instance_command(
                "accessControl.openDoor", {"channel": channel - 1},
                {"DoorIndex": 0, "ShortNumber": short_number},
                None, None, timeout
            )
        except asyncio.TimeoutError:
            raise HomeAssistantError("timeout")
