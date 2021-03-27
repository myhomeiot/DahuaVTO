"""Platform for sensor integration."""
import json
import struct
import asyncio
import hashlib
import logging

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, \
    CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT

DOMAIN = "dahua_vto"
DAHUA_PROTO_DHIP = 0x5049484400000020
DAHUA_HEADER_FORMAT = "<QLLQQ"
DAHUA_REALM_DHIP = 268632079  # DHIP REALM Login Challenge
DAHUA_LOGIN_PARAMS = {
    "clientType": "", "ipAddr": "(null)", "loginType": "Direct"}

DEFAULT_NAME = "Dahua VTO"
DEFAULT_PORT = 5000
DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(
        hass, config, add_entities, discovery_info=None
):
    """Set up the sensor platform."""
    name = config[CONF_NAME]
    entity = DahuaVTO(hass, name, config)
    hass.data[DOMAIN][name] = entity
    hass.loop.create_task(entity.async_run())
    add_entities([entity])
    return True


class DahuaVTOClient(asyncio.Protocol):

    def __init__(self, hass, name, username, password, on_connection_lost):
        self.name = name
        self.hass = hass
        self.username = username
        self.password = password
        self.loop = asyncio.get_running_loop()
        self.on_connection_lost = on_connection_lost

        self.request_id = 0
        self.sessionId = 0
        self.chunk_remaining = 0
        self.chunk = None
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
        if not self.on_connection_lost.done():
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
            self.keepAliveInterval = params.get("keepAliveInterval")
            if self.keepAliveInterval is None:
                raise Exception("keepAliveInterval")
            if self.heartbeat is not None:
                raise Exception("Heartbeat already run")
            self.heartbeat = self.loop.create_task(self.heartbeat_loop())
            self.send({"method": "eventManager.attach",
                       "params": {"codes": ["All"]}})
        elif message.get("method") == "client.notifyEventStream":
            for message in params.get("eventList"):
                message["name"] = self.name
                self.hass.bus.fire(DOMAIN, message)

    def data_received(self, data):
        try:
            if self.chunk_remaining > 0:
                packet = data.decode("utf-8", "ignore")
                self.chunk += packet
                self.chunk_remaining -= len(packet)
                if self.chunk_remaining > 0:
                    return
                elif self.chunk_remaining < 0:
                    raise Exception(f"Remaining bytes {self.chunk_remaining}")
                packet = self.chunk
                self.chunk = None
            else:
                header = struct.unpack(DAHUA_HEADER_FORMAT, data[0:32])
                if header[0] != DAHUA_PROTO_DHIP:
                    raise Exception("Wrong proto")
                packet = data[32:].decode("utf-8", "ignore")
                if header[4] > len(packet):
                    self.chunk = packet
                    self.chunk_remaining = header[4] - len(packet)
                    return

            _LOGGER.debug("<<< {}".format(packet.strip("\n")))
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

    async def command(self, message):
        self.on_response = self.loop.create_future()
        self.on_response_id = self.send(message)
        try:
            return await asyncio.wait_for(self.on_response, timeout=5)
        finally:
            self.on_response = self.on_response_id = None

    async def open_door(self, channel, short_number):
        object_id = await self.command({
            "method": "accessControl.factory.instance",
            "params": {"channel": channel}})
        if object_id.get("result"):
            try:
                await self.command({
                    "method": "accessControl.openDoor", "object": object_id,
                    "params": {"DoorIndex": 0, "ShortNumber": short_number}})
            finally:
                await self.command({
                    "method": "accessControl.destroy", "object": object_id})

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
                        self.hass, self._name, self.config[CONF_USERNAME],
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
