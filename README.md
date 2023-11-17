# PyP100

PyP100 is a Python library for controlling many of the TP-Link Tapo devices including the P100, P105, P110 plugs and the
L530 and L510E bulbs.

This fork is designed to support the new authentication method and is currently compatible with the P100
version 1.2.1. It also supports the old authentication method.

Most of the code originates from [OctoPrint-PSUControl-Tapo](https://github.com/dswd/OctoPrint-PSUControl-Tapo).

Make sure the password of your Tapo account adheres to Tapo's security policy otherwise you'll get a 1003 error (bad login). Currently it requires 2 types of characters (letters, numbers, capitals, symbols).

## Installation

PyP100 can be installed using the package manager [pip](https://pip.pypa.io/en/stable/).

```bash
pip install git+https://github.com/almottier/TapoP100.git@main
```

## Usage

#### Plugs - P100, P105 etc.

```python
from PyP100 import PyP100

p100 = PyP100.P100("192.168.X.X", "email@gmail.com", "Password123")  # Creates a P100 plug object

p100.turnOn()  # Turns the connected plug on
p100.turnOff()  # Turns the connected plug off
p100.toggleState()  # Toggles the state of the connected plug

p100.getDeviceInfo()  # Returns dict with all the device info of the connected plug
p100.getDeviceName()  # Returns the name of the connected plug set in the app

p100.handshake()  # DEPRECATED
p100.login()  # DEPRECATED
```

#### Old Authentication Method

The old authentication method is used as a fallback if the new authentication method fails. It can be forced by setting
the `preferred_protocol` parameter to "old" when creating the plug object.

```python
from PyP100 import PyP100

p100 = PyP100.P100("192.168.X.X", "email@gmail.com", "Password123",
                   preferred_protocol="old")  # Creates a P100 plug object using the old authentication method only
```

#### Bulbs - L530, L510E etc.

```python
from PyP100 import PyL530

l530 = PyL530.L530("192.168.X.X", "email@gmail.com", "Password123")

# All the bulbs have the same basic functions as the plugs and additionally allow for the following functions.
l530.setBrightness(50)  # Sets the brightness of the connected bulb to 50% brightness
l530.setColorTemp(2700)  # Sets the color temperature of the connected bulb to 2700 Kelvin (Warm White)
l530.setColor(30, 80)  # Sets the color of the connected bulb to Hue: 30°, Saturation: 80% (Orange)
```

#### Energy Monitoring - P110

```python
from PyP100 import PyP110

p110 = PyP110.P110("192.168.X.X", "email@gmail.com", "Password123")

# The P110 has all the same basic functions as the plugs and additionally allow for energy monitoring.
p110.getEnergyUsage()  # Returns dict with all of the energy usage of the connected plug
```

## Contributing

Contributions are always welcome!

Please submit a pull request or open an issue for any changes.

## License

[MIT](https://choosealicense.com/licenses/mit/)

