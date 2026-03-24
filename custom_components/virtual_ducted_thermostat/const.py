"""VirtualDucted thermostat's constant """
from homeassistant.components.climate import (
    HVACMode,
)

#Generic
VERSION = '0.1'
DOMAIN = 'virtual_ducted_thermostat'
PLATFORM = 'climate'
ISSUE_URL = 'https://github.com/thecowan/climate.virtual_ducted_thermostat/issues'
CONFIGFLOW_VERSION = 4


#Defaults
DEFAULT_TOLERANCE = 0.5
DEFAULT_PARASITIC_TOLERANCE = 0.3
DEFAULT_NAME = 'Virtual Ducted Thermostat'
DEFAULT_MAX_TEMP = 40
DEFAULT_MIN_TEMP = 5
DEFAULT_MIN_CYCLE_DURATION = '05:00'

#Others
MAX_HVAC_OPTIONS = 8
INITIAL_HVAC_MODE_OPTIONS = ['', HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF, HVACMode.HEAT_COOL]
INITIAL_HVAC_MODE_OPTIONS_OPTFLOW = ['null', HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF, HVACMode.HEAT_COOL]
REGEX_STRING = r'((?P<hours>\d+?):(?=(\d+?:\d+?)))?((?P<minutes>\d+?):)?((?P<seconds>\d+?))?$'

#Attributes
ATTR_VENT_SWITCH_IDS = "vent_switch_ids"
ATTR_SENSOR_ID = "sensor_id"
ATTR_PRESET_TEMPERATURES = "preset_temperatures"
