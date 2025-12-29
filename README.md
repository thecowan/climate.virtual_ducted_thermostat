# VIRTUAL DUCTED THERMOSTAT
This component takes an existing Home Assistant `climate` entity and a number of `switch` entities representing A/C vents with a corresponding number of `sensor` entities providing temperature readings, and creates a number of virtual `climate` entities representing different rooms/areas. It then coordinates between the virtual entities to control the underlying 'real' entity (for example, if the "Bedroom" temperature sensor indicates that the "Bedroom" virtual climate, in cooling mode, needs to lower the temperature, then it will turn on the underlying 'real' climate entity (if it's off), open the "Bedroom" vent switch, and run until temperature is in range, then close the vent (and shut down the 'real' entity if that was the last vent open.

## HOW TO INSTALL
**Currently unsupported**: ~~Use HACS to install the custom component and configure it through the user interface (settings/integration) to have easy and smooth usage.~~

If you are for the manual method:
Just copy paste the content of the `climate.virtual_ducted_thermostat/custom_components` folder in your `config/custom_components` directory.

For example, you will get the '.py' file in the following path: `/config/custom_components/virtual_ducted_thermostat/climate.py`.

## EXAMPLE OF SETUP
Config flow is available, so just configure all the entities you want through the user interface.

Here is a reasonably comprehensive example of manual setup of sensor and possible parameters to configure.
```yaml
climate:
  - platform: virtual_ducted_thermostat
    name: Virtual Climate Controller
    central_climate: climate.daikin_ac
    tolerance: 0.5
    parasitic_tolerance: 0.3
    auto_mode: all
    min_cycle_duration:
      minutes: 1
    preset_modes:
      - sleep
      - away
    max_temp: 30
    min_temp: 10
    initial_hvac_mode: COOL
    zone:
      - name: "Bedroom"
        vent_switch: switch.daikin_ac_bedroom
        temp_sensor: sensor.bedroom_temperature
        humidity_sensor: sensor.bedroom_humidity
        unique_id: vdt_daikin_ac_bedroom
      - name: "Living Room"
        vent_switch: switch.daikin_ac_living
        temp_sensor: sensor.living_room_temperature
        humidity_sensor: sensor.living_room_humidity
        unique_id: vdt_daikin_ac_living
        # The below allow a single zone to override the defaults specified at the level above.
        max_temp: 25 
        min_temp: 15
        tolerance: 1.5
        parasitic_tolerance: 1.0
        auto_mode: all
```


**BELOW INFORMATION IS NOT CORRECT, NEED TO UPDATE** 

**TODO(thecowan)**: update this


Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `programmable_thermostat` | *Required* |
name| Programmable Thermostat | Optional |
heater |  | *Conditional* | Switch that will activate/deactivate the heating system. This can be a single entity or a list of entities. At least one between `heater` and `cooler` has to be defined.
cooler |  | *Conditional* | Switch that will activate/deactivate the cooling system.  This can be a single entity or a list of entities. At least one between `heater` and `cooler` has to be defined.
actual_temp_sensor |  | *Required* | Sensor of actual room temperature.
min_temp | 5 | Optional | Minimum temperature manually selectable.
max_temp | 40 | Optional | Maximum temperature manually selectable.
target_temp_sensor |  | *Required* | Sensor that represent the desired temperature for the room. Suggestion: use my [`file_restore`][1] component or something similar.
tolerance | 0.5 | Optional | Tolerance for turn on and off the switches mode.
initial_hvac_mode | `heat_cool`, `heat`, `cool`, `off` | Optional | If not set, components will restore old state after restart. I suggest not to use it.
related_climate |  | Optional | To be used if the climate object is a slave of another one. below 'Related climate' chapter a description.
hvac_options | 7 | Optional | This defines which combination of manual-auto-off options you want to activate. Refer to the chapter below for the value.
auto_mode | `all`, `heating`, `cooling` | Optional | This allows limiting the heating/cooling function with HVAC mode HEAT_COOL.
min_cycle_duration |  | Optional | TIMEDELTA type. This will allow protecting devices that request a minimum type of work/rest before changing status. On this, you have to define hours, minutes and/or seconds as son elements.

## SPECIFICITIES
### TARGET TEMPERATURE SENSOR
`target_temp_sensor` is the Home Assistant `entity_id` of a sensor which' state change accordingly a specified temperature profile. This temperature profile should describe the desired temperature for the room each day/hour.
`target_temp_sensor` must have a temperature value (a number with or without decimal) as a state.

### ADDITIONAL INFO
The programmed temperature will change accordingly to the one set by the `target_temp_sensor` when in `heat_cool` mode. You can still change it temporarily with the slider. Target temperature will be set, again, to the one of `target_temp_sensor` at its first change.
`heat` and `cool` modes are the manual mode; in this mode, the planning will not be followed.

After a restart of Home Assistant, room temperature and planned room temperature will match till `actual_temp_sensor` will return a temperature value.
This is done to avoid possible issues with Homekit support with a temperature sensor that needs some time to sync with Home Assistant.

### HVAC OPTIONS
This parameter allows you to define which mode you want to activate for that climate object. This is a number with a meaning of every single bit. Here below the table.

bit3 - AUTOMATIC | bit2 - MANUAL | bit1 - OFF | RESULT | Meaning
--- | --- | --- | --- | ---
0 | 0 | 0 | 0 | Noting active - USELESS
0 | 0 | 1 | 1 | OFF only
0 | 1 | 0 | 2 | MANUAL only, you will have only `heat` and/or `cool` modes
0 | 1 | 1 | 3 | MANUAL and OFF
1 | 0 | 0 | 4 | AUTOMATIC only, you will have only `heat_cool` modes
1 | 0 | 1 | 5 | AUTOMATIC and OFF
1 | 1 | 0 | 6 | AUTOMATIC and MANUAL
1 | 1 | 1 | 7 | DEAFAULT - Full mode, you will have active all the options.

### HEATERS AND COOLER SPECIFICS
From version 7.6 you will be able to set `heaters` and `coolers` to the same list and you'll get the correct way of work in manual mode.
This means that `heat` and `cool` mode will work correctly with the same list, but `heat_cool` mode will not (otherwise you will not be able to switch the real device between the 2 modes).
My suggestion is to set `hvac_options: 3` to remove the auto mode.

***
~~Everything is available through HACS.~~

##### CREDITS

The original code for this project is a fork of MapoDan's [Programmable Thermostat](https://github.com/custom-components/climate.programmable_thermostat). Thanks MapoDan for making this project so much easier!

Icons made by <a href="https://www.flaticon.com/authors/freepik" title="Freepik">Freepik</a> from <a href="https://www.flaticon.com/" title="Flaticon"> www.flaticon.com</a>
