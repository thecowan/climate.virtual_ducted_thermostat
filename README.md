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
    min_cycle_duration:
      minutes: 1
    preset_modes:
      - sleep
      - away
    max_temp: 30
    min_temp: 10
    initial_hvac_mode: cool
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
```

### Top-level config

Field | Value | Necessity | Comments
--- | --- | --- | ---
platform | `virtual_ducted_thermostat` | *Required* |
central_climate |   | *Required* | Underlying central climate entity that will be controlled to direct temperature to each zone.
zone |   | *Required* | List of `zone` structures (see next section) for each individual virtual zone within the system.
name | Virtual Ducted Thermostat | Optional |
min_temp | 5 | Optional | Minimum temperature manually selectable.
max_temp | 40 | Optional | Maximum temperature manually selectable.
tolerance | 0.5 | Optional | Tolerance for turning on and off the switches.
parasitic_tolerance |  | Optional | A different tolerance to use if another zone is on. For example, a 0.5 degree tolerance on a 20-degree cooling setpoint won't open the vent until the temperature reaches 20.5; if `parasitic_tolerance` is set to 0.3, then that means the zone will be willing to open the vent at only 20.3 degrees. This tries to reduce cycle churn, where Zone A turns on, cools, turns off, and zone B then turns on soon after, by 'encouraging' zones to operate in parallel.
min_cycle_duration |  | Optional | TIMEDELTA type. This will allow protecting devices that request a minimum type of work/rest before changing status. On this, you have to define hours, minutes and/or seconds as son elements.
initial_hvac_mode | `heat_cool`, `heat`, `cool`, `off` | Optional | If not set, components will restore old state after restart. I suggest not to use it.
preset_mode | (none) | Optional | A list of preset modes that the entities should expose.

### Per-zone config

Field | Value | Necessity | Comments
--- | --- | --- | ---
name |  | *Required* |
vent_switch |  | *Required* | The entity ID of the underlying `switch` which needs to open/close to enable this zone.
temp_sensor |  | *Required* | The entity ID of a `sensor` which indicates the current temperature in the zone.
humidity_sensor |  | Optional | The entity ID of a `sensor` which indicates the current humidity in the zone. Will simply be passed through (e.g. exposed as the humidity of the climate entity created) if supplied.
unique_id |  | Optional | Unique per-device, allows customisation of the climate entity in the Home Assistant UI.
min_temp | | Optional | Overrides the global default (see previous section)
max_temp | | Optional | Overrides the global default (see previous section)
tolerance | | Optional | Overrides the global default (see previous section)
parasitic_tolerance |  | Optional | Overrides the global default (see previous section)

**BELOW INFORMATION IS NOT CORRECT, NEED TO UPDATE** 

**TODO(thecowan)**: update this
    

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
