"""Adds support for generic thermostat units."""
import asyncio
import logging
import json
from datetime import timedelta
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity, DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    ATTR_HVAC_MODE,
    ATTR_FAN_MODE
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval
)
from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    VERSION,
    DOMAIN,
    PLATFORM,
    ATTR_VENT_SWITCH_IDS,
    ATTR_SENSOR_ID
)
from .config_schema import(
    CLIMATE_SCHEMA,
    CONF_VENT_SWITCH,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TOLERANCE,
    CONF_INITIAL_HVAC_MODE,
    CONF_CENTRAL_CLIMATE,
    CONF_AUTO_MODE,
    CONF_MIN_CYCLE_DURATION,
    CONF_ZONE,
    CONF_ZONE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_UNIQUE_ID,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP
)
from .helpers import dict_to_timedelta

_LOGGER = logging.getLogger(__name__)

__version__ = VERSION

DEPENDENCIES = ['switch', 'sensor']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLIMATE_SCHEMA)

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Add VirtualDuctedThermostat entities from configuration.yaml."""
    _LOGGER.info("Setup entity coming from configuration.yaml named: %s", config.get(CONF_NAME))
    await async_setup_reload_service(hass, DOMAIN, PLATFORM)
    async_add_entities(VirtualThermostatHolder(hass, config).climate_entities)

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add VirtualDuctedThermostat entities from configuration flow."""
    result = {}
    if config_entry.options != {}:
        result = config_entry.options
    else:
        result = config_entry.data
    _LOGGER.info("setup entity-config_entry_data=%s",result)
    await async_setup_reload_service(hass, DOMAIN, PLATFORM)

    async_add_devices([VirtualDuctedThermostat(hass, result)])


class VirtualThermostatHolder():
    def __init__(self, hass, config):
        self.hass = hass
        #self._name = config.get(CONF_NAME)
        self.climate_entities = [VirtualDuctedThermostat(hass, self, config, zoneconfig) for zoneconfig in config[CONF_ZONE]]
        self._central_climate = config.get(CONF_CENTRAL_CLIMATE)
        self._unit = hass.config.units.temperature_unit
        # TODO- attributes summarizing state?


class VirtualDuctedThermostat(ClimateEntity, RestoreEntity):
    """VirtualDuctedThermostat."""
    def __init__(self, hass, holder, config, zoneconfig):
        """Initialize the thermostat."""
        self.holder = holder
        self.hass = hass
        self._name = zoneconfig.get(CONF_NAME)
        self.vent_switch_entity_ids = self._getEntityList(zoneconfig.get(CONF_VENT_SWITCH))
        self.sensor_entity_id = zoneconfig.get(CONF_ZONE_SENSOR)
        self._unique_id = zoneconfig.get(CONF_UNIQUE_ID)
        self._humidity_sensor_id = zoneconfig.get(CONF_HUMIDITY_SENSOR)

        self._tolerance = zoneconfig.get(CONF_TOLERANCE)
        if self._tolerance == None:
          self._tolerance = config.get(CONF_TOLERANCE)

        self._clone_min = False
        self._clone_max = False
        self._min_temp = zoneconfig.get(CONF_MIN_TEMP)
        if self._min_temp == None:
            self._min_temp = config.get(CONF_MIN_TEMP)
        if self._min_temp == None:
            self._clone_min = True
            self._min_temp = DEFAULT_MIN_TEMP

        self._max_temp = zoneconfig.get(CONF_MAX_TEMP)
        if self._max_temp == None:
            self._max_temp = config.get(CONF_MAX_TEMP)
        if self._max_temp == None:
            self._clone_max = True
            self._max_temp = DEFAULT_MAX_TEMP

        self._auto_mode = zoneconfig.get(CONF_AUTO_MODE)
        if self._auto_mode == None:
            self._auto_mode = config.get(CONF_AUTO_MODE)

        self._initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
        self._hvac_list = []
        self.min_cycle_duration = config.get(CONF_MIN_CYCLE_DURATION)
        if type(self.min_cycle_duration) == type({}):
            self.min_cycle_duration = dict_to_timedelta(self.min_cycle_duration)
        # self._target_temp = self._getFloat(self._getStateSafe(self.target_entity_id), None)
        # TODO
        self._target_temp = float((self._min_temp + self._max_temp)/2)
        self._cur_temp = self._getFloat(self._getStateSafe(self.sensor_entity_id), self._target_temp)
        self._active = False
        self._temp_lock = asyncio.Lock()

        self._hvac_list.append(HVAC_MODE_OFF)
        self._hvac_action = HVACAction.IDLE
        if self._initial_hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
        elif self._initial_hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
        elif self._initial_hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
        else:
            self._hvac_mode = HVAC_MODE_OFF
            self._hvac_action = HVACAction.OFF

        self._supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._supported_fan_modes = []
        self._fan_mode = None
        self._cur_humidity = None
        self._initialized_options = False
        self._awaiting_climate_state = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.sensor_entity_id, self._async_sensor_changed))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.vent_switch_entity_ids, self._async_switch_changed))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.holder._central_climate, self._async_climate_changed))
        if self._humidity_sensor_id != None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._humidity_sensor_id, self._async_humidity_changed))


        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self._getStateSafe(self.sensor_entity_id)
            if sensor_state and sensor_state != STATE_UNKNOWN:
                self._async_update_temp(sensor_state)
            if self._humidity_sensor_id != None:
                humidity_state = self._getStateSafe(self._humidity_sensor_id)
                if humidity_state and humidity_state != STATE_UNKNOWN:
                    self._async_update_humidity(humidity_state)
            climate_state = self.hass.states.get(self.holder._central_climate)
            if climate_state and climate_state.state != STATE_UNKNOWN and not self._initialized_options:
                self._initialize_options(climate_state)

            #TODO
            #target_state = self._getStateSafe(self.target_entity_id)
            #if target_state and \
            #   target_state != STATE_UNKNOWN and \
            #   self._hvac_mode != HVAC_MODE_HEAT_COOL:
            #    self._async_update_program_temp(target_state)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        _LOGGER.info("climate.%s old state: %s", self._name, old_state)
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    #target_entity_state = self._getStateSafe(self.target_entity_id)
                    #if target_entity_state is not None:
                    #    self._target_temp = float(target_entity_state)
                    #else:
                    self._target_temp = float((self._min_temp + self._max_temp)/2)
                    _LOGGER.warning("climate.%s - Undefined target temperature,"
                                    "falling back to %s", self._name , self._target_temp)
                else:
                    self._target_temp = float(
                        old_state.attributes[ATTR_TEMPERATURE])
            if (self._initial_hvac_mode is None and
                    old_state.state is not None):
                self._hvac_mode = \
                    old_state.state
                self._enabled = self._hvac_mode != HVAC_MODE_OFF

        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                self._target_temp = float((self._min_temp + self._max_temp)/2)
            _LOGGER.warning("climate.%s - No previously saved temperature, setting to %s", self._name,
                            self._target_temp)

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    def _initialize_options(self, climate_state):
        _LOGGER.debug("climate.%s initializing options based on state %s", self._name, climate_state)
        # TODO: handle heat_cool specially
        for mode in climate_state.attributes['hvac_modes']:
            if mode == HVAC_MODE_OFF:
                # Skip
                pass
            else:
                # TODO: move this to the enum
                self._hvac_list.append(str(mode))
        _LOGGER.debug("climate.%s my supported modes now %s", self._name, self._hvac_list)

        if (climate_state.attributes['supported_features'] & ClimateEntityFeature.FAN_MODE) != 0:
            self._supported_features |= ClimateEntityFeature.FAN_MODE
            # TODO don't hardcode this!
            self._supported_fan_modes = [mode for mode in climate_state.attributes['fan_modes'] if "/" not in mode]
            self._fan_mode = climate_state.attributes['fan_mode']
            _LOGGER.debug("climate.%s my supported fan modes now %s, initial mode %s", self._name, self._supported_fan_modes, self._fan_mode)

        if self._clone_min:
            climate_temp = climate_state.attributes['min_temp']
            if climate_temp == None:
              _LOGGER.debug("climate.%s didn't get a min temp in config, but central doesn't have one either", self._name)
            else:
              _LOGGER.debug("climate.%s didn't get a min temp in config, copying from central climate (%s)", self._name, climate_temp)
            self._min_temp = float(climate_temp)

        if self._clone_max:
            climate_temp = climate_state.attributes['max_temp']
            if climate_temp == None:
              _LOGGER.debug("climate.%s didn't get a max temp in config, but central doesn't have one either", self._name)
            else:
              _LOGGER.debug("climate.%s didn't get a max temp in config, copying from central climate (%s)", self._name, climate_temp)
            self._max_temp = float(climate_temp)

        self._initialized_options = True

    async def control_system_mode(self):
        """this is used to decide what to do, so this function turn off switches and run the function
           that control the temperature."""
        if self._hvac_mode == HVAC_MODE_OFF:
            _LOGGER.debug("climate.%s set to off", self._name)
            # TODO this isn't right but I don't think it matters
            await self._async_turn_off(mode="heat")
            self._hvac_action = HVACAction.OFF
        elif self._hvac_mode == HVAC_MODE_HEAT:
            _LOGGER.debug("climate.%s set to heat", self._name)
            await self._async_control_thermo(mode="heat")
        elif self._hvac_mode == HVAC_MODE_COOL:
            _LOGGER.debug("climate.%s set to cool", self._name)
            await self._async_control_thermo(mode="cool")
        elif self._hvac_mode == HVAC_MODE_HEAT_COOL:
            _LOGGER.debug("climate.%s set to auto", self._name)
            for opmod in self._hvac_list:
            # Check of self._auto_mode has been added to avoid cooling a room that has just been heated and vice versa
            # LET'S PRESERVE ENERGY!
            # If you don't want to check that you have just to set auto_mode=all
                if opmod is HVAC_MODE_HEAT and self._auto_mode != 'cooling':
                    _LOGGER.debug("climate.%s - Entered here in heating mode", self._name)
                    await self._async_control_thermo(mode="heat")
                if opmod is HVAC_MODE_COOL and self._auto_mode != 'heating':
                    _LOGGER.debug("climate.%s - Entered here in cooling mode", self._name)
                    await self._async_control_thermo(mode="cool")
        elif self._hvac_mode == HVAC_MODE_FAN_ONLY:
            _LOGGER.debug("climate.%s set to fan only", self._name)
            await self._async_control_non_thermo()
        elif self._hvac_mode == HVAC_MODE_DRY:
            _LOGGER.debug("climate.%s set to dry", self._name)
            await self._async_control_non_thermo()
        else:
            _LOGGER.debug("climate.%s set to unrecognised mode - %s, skipping control", self._name, self._hvac_mode)
        return

    async def _async_turn_on(self, mode=None):
        """Turn toggleable device on."""
        # TODO - is happening even if that's already the mode we're in
        vent_data = {ATTR_ENTITY_ID: self.vent_switch_entity_ids}
        if mode in (HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY):
            central_data = {ATTR_ENTITY_ID: self.holder._central_climate, ATTR_HVAC_MODE: mode}
        else:
            _LOGGER.error("climate.%s - No type has been passed to turn_on function", self._name)
            return

        if not self._is_device_active_function() and not self.is_active_long_enough(mode=mode):
            _LOGGER.error("climate.%s - can't turn on, device not active long enough", self._name)
            # TODO - reschedule?
            return

        self._set_hvac_action_on(mode=mode)
        if not self._areAllInState(self.vent_switch_entity_ids, STATE_ON):
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, vent_data)
        await self.hass.services.async_call(CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, central_data)
        await self.async_update_ha_state()

    async def _async_turn_off(self, mode=None):
        """Turn heater toggleable device off."""
        # central_climate_hvac_action = self.hass.states.get(self.holder._central_climate).attributes['hvac_action']
        # TODO if central_climate_hvac_action == CURRENT_HVAC_HEAT or central_climate_hvac_action == CURRENT_HVAC_COOL:
        #    _LOGGER.info("climate.%s - Central climate object action is %s, so no action taken.", self._name, central_climate_hvac_action)
        #    return
        vent_data = {ATTR_ENTITY_ID: self.vent_switch_entity_ids}
        #if mode == "heat":
        #    #TODO
        #    central_data = {ATTR_ENTITY_ID: self.holder._central_climate, ATTR_HVAC_MODE: HVAC_MODE_OFF}
        #elif mode == "cool":
        #    central_data = {ATTR_ENTITY_ID: self.holder._central_climate, ATTR_HVAC_MODE: HVAC_MODE_OFF}
        #else:
        #    _LOGGER.error("climate.%s - No type has been passed to turn_off function", self._name)
        if self._is_device_active_function() and self.is_active_long_enough(mode=mode):
            self._set_hvac_action_off(mode=mode)
            # TODO: don't seem to be turning off?
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, vent_data)
            #await self.hass.services.async_call(CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, central_data)
            await self.async_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode not in self._hvac_list:
            _LOGGER.error("climate.%s - Unrecognized hvac mode: %s", self._name, hvac_mode)
            return

        self._hvac_mode = hvac_mode
        await self.control_system_mode()
        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        if fan_mode not in self._supported_fan_modes:
            _LOGGER.error("climate.%s - Unrecognized fan mode: %s", self._name, fan_mode)
            return

        self._fan_mode = fan_mode
        # TODO - is happening even if that's already the mode we're in
        central_data = {ATTR_ENTITY_ID: self.holder._central_climate, ATTR_FAN_MODE: fan_mode}
        await self.hass.services.async_call(CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE, central_data)
        await self.async_update_ha_state()
        self.async_update_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._async_update_temp(new_state.state)
        await self.control_system_mode()
        await self.async_update_ha_state()

    async def _async_humidity_changed(self, event):
        """Handle humidity changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._async_update_humidity(new_state.state)
        await self.async_update_ha_state()

    async def _async_control_thermo(self, mode=None):
        """Check if we need to turn heating on or off."""
        if self._cur_temp is None:
            _LOGGER.info("climate.%s - Abort _async_control_thermo as _cur_temp is None", self._name)
            return
        if self._target_temp is None:
            _LOGGER.info("climate.%s - Abort _async_control_thermo as _target_temp is None", self._name)
            return

        # TODO
        if mode == "heat":
            hvac_mode = HVAC_MODE_COOL
            delta = self._target_temp - self._cur_temp
            entities = self.vent_switch_entity_ids
        elif mode == "cool":
            hvac_mode = HVAC_MODE_HEAT
            delta = self._cur_temp - self._target_temp
            entities = self.vent_switch_entity_ids
        else:
            _LOGGER.error("climate.%s - No type has been passed to control_thermo function", self._name)
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp,
                                                 self._target_temp):
                self._active = True
                _LOGGER.debug("climate.%s - Obtained current and target temperature. "
                             "Generic thermostat active. %s, %s", self._name,
                             self._cur_temp, self._target_temp)

            if not self._active or self._hvac_mode == HVAC_MODE_OFF or self._hvac_mode == hvac_mode:
                return

            # TODO - not actually opening here?
            if delta <= 0:
                if not self._areAllInState(entities, STATE_OFF):
                    _LOGGER.debug("Turning off %s", entities)
                    await self._async_turn_off(mode=mode)
                self._set_hvac_action_off(mode=mode)
            elif delta >= self._tolerance:
                self._set_hvac_action_on(mode=mode)
                if not self._areAllInState(entities, STATE_ON):
                    _LOGGER.debug("Turning on %s", entities)
                    await self._async_turn_on(mode=mode)

    async def _async_control_non_thermo(self):
        _LOGGER.debug("climate.%s - Entering non-thermo control, mode %s", self._name, self._hvac_mode)
        entities = self.vent_switch_entity_ids
        async with self._temp_lock:
            if self._hvac_mode == HVAC_MODE_OFF:
                return

            _LOGGER.debug("climate.%s - Turning on HVAC action", self._name)
            self._set_hvac_action_on(mode=self._hvac_mode)
            _LOGGER.debug("climate.%s - Turning on %s", self._name, entities)
            await self._async_turn_on(mode=self._hvac_mode)

    def _set_hvac_action_off(self, mode=None):
        """This is used to set CURRENT_HVAC_OFF on the climate integration.
           This has been split form turn_off function since this will allow to make dedicated calls.
           For the other CURRENT_HVAC_*, this is not needed becasue they work perfectly at the turn_on."""
        # This if condition is necessary to correctly manage the action for the different modes.
        _LOGGER.debug("climate.%s - mode=%s \r\ntarget=%s \r\n current=%s", self._name, mode, self._target_temp, self._cur_temp)
        # TODO
        if mode == "heat":
            delta = self._target_temp - self._cur_temp
            entities = self.vent_switch_entity_ids
            mode_2 = "cool"
        elif mode == "cool":
            delta = self._cur_temp - self._target_temp
            entities = self.vent_switch_entity_ids
            mode_2 = "heat"
        else:
            _LOGGER.error("climate.%s - No type has been passed to _set_hvac_action_off function", self._name)
            mode_2 = None
        _LOGGER.debug("climate.%s - delta=%s", self._name, delta)
        if (((mode == "cool" and not self._hvac_mode == HVAC_MODE_HEAT) or \
           (mode == "heat" and not self._hvac_mode == HVAC_MODE_COOL)) and \
           not self._hvac_mode == HVAC_MODE_HEAT_COOL):
            # TODO: true, or idle?
            self._hvac_action = HVACAction.OFF
            _LOGGER.debug("climate.%s - new action %s", self._name, self._hvac_action)
        elif self._hvac_mode == HVAC_MODE_HEAT_COOL and delta <= 0:
            # TODO: true, or off?
            self._hvac_action = HVACAction.OFF
            _LOGGER.debug("climate.%s - new action %s", self._name, self._hvac_action)
            if abs(delta) >= self._tolerance and entities != None:
                self._set_hvac_action_on(mode=mode_2)
        else:
            if not self._is_device_active_function():
                self._hvac_action = HVACAction.OFF
            else:
                _LOGGER.error("climate.%s - Error during set of HVAC_ACTION", self._name)

    def _set_hvac_action_on(self, mode=None):
        """This is used to set CURRENT_HVAC_* according to the mode that is running."""
        if mode == HVAC_MODE_HEAT:
            self._hvac_action = HVACAction.HEATING
        elif mode == HVAC_MODE_COOL:
            self._hvac_action = HVACAction.COOLING
        elif mode == HVAC_MODE_DRY:
            self._hvac_action = HVACAction.DRYING
        elif mode == HVAC_MODE_FAN_ONLY:
            self._hvac_action = HVACAction.FAN
        else:
            _LOGGER.error("climate.%s - No type has been passed to turn_on function", self._name)
            return
        _LOGGER.debug("climate.%s - new action %s caused by mode %s", self._name, self._hvac_action, mode)

    def _getEntityList(self, entity_ids):
        if entity_ids is not None:
            if not isinstance(entity_ids, list):
                return [ entity_ids ]
            elif len(entity_ids)<=0:
                return None
        return entity_ids

    def _getStateSafe(self, entity_id):
        full_state = self.hass.states.get(entity_id)
        if full_state is not None:
            return full_state.state
        return None

    def _getFloat(self, valStr, defaultVal):
        if valStr!=STATE_UNKNOWN and valStr!=STATE_UNAVAILABLE and valStr is not None:
            return float(valStr)
        return defaultVal

    def _areAllInState(self, entity_ids, state):
        for entity_id in entity_ids:
            if not self.hass.states.is_state(entity_id, state):
                return False
        return True


    def _is_device_active_function(self):
        """If the toggleable device is currently active."""
        _LOGGER.debug("climate.%s - vent switches: %s", self._name, self.vent_switch_entity_ids)
        return self._areAllInState(self.vent_switch_entity_ids, STATE_ON)

    def is_active_long_enough(self, mode=None):
        """ This function is to check if the heater/cooler has been active long enough """
        if not self.min_cycle_duration:
            return True
        if self._is_device_active:
            current_state = STATE_ON
        else:
            current_state = STATE_OFF
        if mode in (HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY, HVAC_MODE_DRY):
            # TODO - exits early by mistake?
            for entity in self.vent_switch_entity_ids:
                return condition.state(self.hass, entity, current_state, self.min_cycle_duration)
        else:
            _LOGGER.error("Wrong mode have been passed to function is_active_long_enough")
        return True

    @callback
    async def _async_switch_changed(self, event):
        """Handle climate switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        _LOGGER.debug("climate.%s - Got a new switch state %s, I'm %s", self._name, new_state, self._hvac_mode)
        if new_state.state == STATE_ON and self._hvac_mode == HVAC_MODE_OFF:
            _LOGGER.debug("climate.%s - I was off, but switch %s has been opened - updating my state", self._name, event.data['entity_id'])
            to_open = []
            for switch in self.vent_switch_entity_ids:
                if switch == event.data['entity_id']:
                    continue
                switch_state = self._getStateSafe(switch)
                if switch_state and switch_state == STATE_OFF:
                    to_open.append(switch)
            if len(to_open) > 0:
                _LOGGER.debug("climate.%s - opening peer switches %s to match", self._name, to_open)
                await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: to_open})

            climate_state = self._getStateSafe(self.holder._central_climate)
            if climate_state is None:
                _LOGGER.debug("climate.%s - climate has no state, waiting to see state update later", self._name)
                self._awaiting_climate_state = True
            elif climate_state == HVAC_MODE_OFF:
                # TODO
                _LOGGER.debug("climate.%s - something's opened my vent, but climate is off. Spooky! Not sure what to do.", self._name)
            else:
                _LOGGER.debug("climate.%s - vent now open, setting my state to %s", self._name, climate_state)
                self._hvac_mode = climate_state
                self._set_hvac_action_on(self.hvac_mode)
        elif new_state.state == STATE_OFF and self._hvac_mode != HVAC_MODE_OFF:
            _LOGGER.debug("climate.%s - I was in mode %s, but switch %s has been closed - turning myself off", self._name, self._hvac_mode, event.data['entity_id'])
            self._hvac_mode = HVAC_MODE_OFF
            await self.control_system_mode()


        self.async_write_ha_state()

    @callback
    async def _async_climate_changed(self, event):
        """Handle central climate state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state != STATE_UNKNOWN and not self._initialized_options:
            self._initialize_options(new_state)

        central_state = new_state.state
        # Should we update our state in response?
        # TODO: implement this as an option
        should_follow = False

        if self._awaiting_climate_state:
            if central_state == HVAC_MODE_OFF:
                _LOGGER.debug("climate.%s - been waiting to climate state for open vent but it's off. Guess I'll keep waiting?", self._name)
            else:
                _LOGGER.debug("climate.%s - finally received climate_state %s, will update myself", self._name, central_state)
                should_follow = True
                self._awaiting_climate_state = False

        my_state = self._hvac_mode
        _LOGGER.debug("climate.%s - New state from climate %s (vs my %s)", self._name, central_state, my_state)

        # TODO: check logic here - should this be based on switch state? Or should that just be checked on startup?
        if (central_state == my_state):
            _LOGGER.debug("climate.%s - No change, nothing to do", self._name)
        elif should_follow:
            _LOGGER.debug("climate.%s - Been told to follow this state change, updating myself", self._name)
            await self.async_set_hvac_mode(central_state)
        elif (my_state == HVAC_MODE_OFF):
          _LOGGER.debug("climate.%s - I'm already off, nothing to do", self._name)
        elif (central_state == HVAC_MODE_OFF):
          # TODO - determine if it turned off manually or because of us
          _LOGGER.debug("climate.%s - central turned off, but I'll stay running", self._name)
        else:
          _LOGGER.debug("climate.%s - Guess I'll turn myself off", self._name)
          await self.async_set_hvac_mode(HVAC_MODE_OFF)

        if (self._supported_features & ClimateEntityFeature.FAN_MODE) != 0:
            new_fan_mode = new_state.attributes['fan_mode']
            if (new_fan_mode == self._fan_mode):
                _LOGGER.debug("climate.%s - No change to fan, nothing to do", self._name)
            else:
                _LOGGER.debug("climate.%s - updating my fan mode to %s", self._name, new_fan_mode)
                self._fan_mode = new_fan_mode

        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to update current temperature from sensor: %s", self._name, ex)

    @callback
    def _async_update_humidity(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_humidity = float(state)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to update current humidity from sensor: %s", self._name, ex)

    @callback
    def _async_update_program_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._target_temp = float(state)
        except ValueError as ex:
            _LOGGER.warning("climate.%s - Unable to update target temperature from sensor: %s", self._name, ex)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.holder._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def current_humidity(self):
        """Return the sensor humidity."""
        return self._cur_humidity

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self._is_device_active_function()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of supported fan modes."""
        return self._supported_fan_modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return self._hvac_action

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._unique_id

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes to be saved. """
        attributes = {}

        attributes[ATTR_VENT_SWITCH_IDS] = self.vent_switch_entity_ids
        attributes[ATTR_SENSOR_ID] = self.sensor_entity_id

        return attributes
