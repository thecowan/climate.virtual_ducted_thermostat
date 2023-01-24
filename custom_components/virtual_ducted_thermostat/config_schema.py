import voluptuous as vol
import logging
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE
)
from homeassistant.const import CONF_NAME, CONF_ENTITIES
from .const import (
    DOMAIN,
    DEFAULT_TOLERANCE,
    DEFAULT_NAME,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_AUTO_MODE,
    DEFAULT_MIN_CYCLE_DURATION,
    AUTO_MODE_OPTIONS,
    INITIAL_HVAC_MODE_OPTIONS,
    INITIAL_HVAC_MODE_OPTIONS_OPTFLOW
)
from .helpers import dict_to_string

_LOGGER = logging.getLogger(__name__)

# Per instance
CONF_CENTRAL_CLIMATE = 'central_climate'
CONF_MIN_CYCLE_DURATION = 'min_cycle_duration'
CONF_ZONE = 'zone'
# TODO Still needed?
CONF_INITIAL_HVAC_MODE = 'initial_hvac_mode'

# Per-instance, but overridable
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_TOLERANCE = 'tolerance'
CONF_AUTO_MODE = 'auto_mode'

# Per-zone
CONF_VENT_SWITCH = 'vent_switch'
CONF_NAME = 'name'
CONF_ZONE_SENSOR = 'temp_sensor'
CONF_UNIQUE_ID = 'unique_id'
CONF_HUMIDITY_SENSOR = 'humidity_sensor'

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_VENT_SWITCH): cv.entity_ids,
    # TODO: can be optional?
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ZONE_SENSOR): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_HUMIDITY_SENSOR): cv.string,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_TOLERANCE): vol.Coerce(float),
    vol.Optional(CONF_AUTO_MODE): vol.In(AUTO_MODE_OPTIONS),
})

CLIMATE_SCHEMA = {
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
    vol.Required(CONF_CENTRAL_CLIMATE): cv.entity_id,
    vol.Optional(CONF_AUTO_MODE, default=DEFAULT_AUTO_MODE): vol.In(AUTO_MODE_OPTIONS),
    vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(INITIAL_HVAC_MODE_OPTIONS),
    vol.Optional(CONF_MIN_CYCLE_DURATION): cv.positive_time_period,
    vol.Required(CONF_ZONE): vol.All(cv.ensure_list, [ZONE_SCHEMA])
}

def get_config_flow_schema(config: dict = {}, config_flow_step: int = 0) -> dict:
    if not config:
        config = {
            CONF_NAME: DEFAULT_NAME,
            CONF_VENT_SWITCH: "",
            CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
            CONF_TOLERANCE: DEFAULT_TOLERANCE,
            CONF_CENTRAL_CLIMATE: "",
            CONF_AUTO_MODE: DEFAULT_AUTO_MODE,
            CONF_INITIAL_HVAC_MODE: "",
            CONF_MIN_CYCLE_DURATION: DEFAULT_MIN_CYCLE_DURATION
        }
    if config_flow_step==1:
        return {
            vol.Optional(CONF_NAME, default=config.get(CONF_NAME)): str,
        }
    elif config_flow_step==4:
        #identical to step 1 but without NAME (better to not change it since it will break configuration)
        #this is used for options flow only
        return {
        }
    elif config_flow_step==2:
        return {
            vol.Required(CONF_MAX_TEMP, default=config.get(CONF_MAX_TEMP)): int,
            vol.Required(CONF_MIN_TEMP, default=config.get(CONF_MIN_TEMP)): int,
            vol.Required(CONF_TOLERANCE, default=config.get(CONF_TOLERANCE)): float
        }
    elif config_flow_step==3:
        return {
            vol.Required(CONF_CENTRAL_CLIMATE, default=config.get(CONF_CENTRAL_CLIMATE)): str,
            vol.Required(CONF_AUTO_MODE, default=config.get(CONF_AUTO_MODE)): vol.In(AUTO_MODE_OPTIONS),
            vol.Optional(CONF_INITIAL_HVAC_MODE, default=config.get(CONF_INITIAL_HVAC_MODE)): vol.In(INITIAL_HVAC_MODE_OPTIONS),
            vol.Optional(CONF_MIN_CYCLE_DURATION, default=config.get(CONF_MIN_CYCLE_DURATION)): str
        }
    elif config_flow_step==5:
        #identical to 3 but with CONF_MIN_CYCLE_DURATION converted in string from dict (necessary since it is always set as null if not used)
        #this is used for options flow only
        return {
            vol.Required(CONF_CENTRAL_CLIMATE, default=config.get(CONF_CENTRAL_CLIMATE)): str,
            vol.Required(CONF_AUTO_MODE, default=config.get(CONF_AUTO_MODE)): vol.In(AUTO_MODE_OPTIONS),
            vol.Optional(CONF_INITIAL_HVAC_MODE, default=config.get(CONF_INITIAL_HVAC_MODE)): vol.In(INITIAL_HVAC_MODE_OPTIONS_OPTFLOW),
            vol.Optional(CONF_MIN_CYCLE_DURATION, default=dict_to_string(config.get(CONF_MIN_CYCLE_DURATION))): str
        }

    return {}
