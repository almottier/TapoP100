import logging
from base64 import b64decode

from PyP100 import MeasureInterval

from .auth_protocol import AuthProtocol, OldProtocol

log = logging.getLogger(__name__)


class Device:
    def __init__(self, address, email, password, preferred_protocol=None, **kwargs):
        self.address = address
        self.email = email
        self.password = password
        self.kwargs = kwargs
        self.protocol = None
        self.preferred_protocol = preferred_protocol

    def _initialize(self):
        protocol_classes = {"new": AuthProtocol, "old": OldProtocol}

        # set preferred protocol if specified
        if self.preferred_protocol and self.preferred_protocol in protocol_classes:
            protocols_to_try = [protocol_classes[self.preferred_protocol]]
        else:
            protocols_to_try = list(protocol_classes.values())

        for protocol_class in protocols_to_try:
            if not self.protocol:
                try:
                    protocol = protocol_class(
                        self.address, self.email, self.password, **self.kwargs
                    )
                    protocol.Initialize()
                    self.protocol = protocol
                except:
                    log.exception(
                        f"Failed to initialize protocol {protocol_class.__name__}"
                    )
        if not self.protocol:
            raise Exception("Failed to initialize protocol")

    def request(self, method: str, params: dict = None):
        if not self.protocol:
            self._initialize()
        return self.protocol._request(method, params)

    def handshake(self):
        if not self.protocol:
            self._initialize()
        return

    def login(self):
        return self.handshake()

    def getDeviceInfo(self):
        return self.request("get_device_info")

    def _get_device_info(self):
        return self.request("get_device_info")

    def _set_device_info(self, params: dict):
        return self.request("set_device_info", params)

    def getDeviceName(self):
        data = self.getDeviceInfo()
        encodedName = data["nickname"]
        name = b64decode(encodedName)
        return name.decode("utf-8")

    def switch_with_delay(self, state, delay):
        return self.request(
            "add_countdown_rule",
            {
                "delay": int(delay),
                "desired_states": {"on": state},
                "enable": True,
                "remain": int(delay),
            },
        )


class Switchable(Device):
    def get_status(self) -> bool:
        return self._get_device_info()["device_on"]

    def set_status(self, status: bool):
        mac = self._get_device_info()["mac"]
        return self._set_device_info({"device_on": status, "terminalUUID": mac})

    def turnOn(self):
        return self.set_status(True)

    def turnOff(self):
        return self.set_status(False)

    def toggleState(self):
        return self.set_status(not self.get_status())

    def turnOnWithDelay(self, delay):
        return self.switch_with_delay(True, delay)

    def turnOffWithDelay(self, delay):
        return self.switch_with_delay(False, delay)


class Metering(Device):
    def getEnergyUsage(self) -> dict:
        return self.request("get_energy_usage")

    def getEnergyData(self, start_timestamp: int, end_timestamp: int, interval: MeasureInterval) -> dict:
        """Hours are always ignored, start is rounded to midnight, first day of month or first of January based on interval"""
        return self.request("get_energy_data", {"start_timestamp": start_timestamp, "end_timestamp": end_timestamp, "interval": interval.value})


class Color(Device):
    def setBrightness(self, brightness: int):
        return self._set_device_info({"brightness": brightness})

    def setColorTemp(self, color_temp: int):
        return self._set_device_info({"color_temp": color_temp})

    def setColor(self, hue, saturation):
        return self._set_device_info(
            {"color_temp": 0, "hue": hue, "saturation": saturation}
        )


class P100(Switchable):
    pass
