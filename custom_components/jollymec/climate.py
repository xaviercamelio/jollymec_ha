"""Support for Jollymec heating devices."""
import asyncio
import logging
import os.path
import sys
import time
from datetime import timedelta, datetime 
import voluptuous as vol 
from typing import Any

from .hajolly import ( 
    ConnectionError,
    Error as JollyMecError,
    UnauthorizedError,
    jollymec,
)

logging.basicConfig(filename='/tmp/jollymec_test.log', format='%(asctime)s %(message)s', level=logging.INFO)
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)
_LOGGER.debug("Debug mode is explicitly enabled.")

requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True

#from . import DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, callback
from homeassistant.const import (ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_UNIQUE_ID ,CONF_ID, EVENT_HOMEASSISTANT_START,)
from homeassistant.const import TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE
from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA 
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    PRESET_AWAY,
    PRESET_NONE,
    PRESET_ECO,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_SLEEP,
    PRESET_ACTIVITY,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    ClimateEntityFeature,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    HVACAction,
    HVACMode,
)

ATTR_DEVICE_ALARM = "alarm_code"
ATTR_DEVICE_STATUS = "device_status"
ATTR_HUMAN_DEVICE_STATUS = "human_device_status"
ATTR_REAL_POWER = "real_power"
ATTR_SMOKE_TEMP = "smoke_temperature"

scan_interval = timedelta(minutes=1)
DEFAULT_NAME = "Jollymec"

CONF_PRESETS = {
    p: f"{p}_temp"
    for p in (
        PRESET_AWAY,
        PRESET_COMFORT,
        PRESET_ECO,
        PRESET_BOOST,
        PRESET_HOME,
        PRESET_SLEEP,
        PRESET_ACTIVITY,
    )
}

CONF_FAN = {
    p: f"{p}_pw"
    for p in (
        PRESET_AWAY,
        PRESET_COMFORT,
        PRESET_ECO,
        PRESET_BOOST,
        PRESET_HOME,
        PRESET_SLEEP,
        PRESET_ACTIVITY,
    )
}

CONF_HEATER = "heater"
CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_AC_MODE = "ac_mode"
CONF_MIN_DUR = "min_cycle_duration"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_PRECISION = "precision"
CONF_TEMP_STEP = "target_temp_step"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HEATER): cv.entity_id,
    vol.Optional(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_ID): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_UNIQUE_ID): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_AC_MODE): cv.boolean,
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MIN_DUR): cv.positive_time_period,
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
    vol.Optional(CONF_KEEP_ALIVE): cv.positive_time_period,
    #vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period
}).extend({vol.Optional(v): vol.Coerce(float) for (k, v) in CONF_PRESETS.items()}).extend({vol.Optional(v): vol.Coerce(int) for (k, v) in CONF_FAN.items()})



async def async_setup_platform(hass, config, async_add_entities,  discovery_info = None):

    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)

    """Set up Jollymec climate, nothing to do."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    heater_id = config.get(CONF_ID)
    unique_id = config.get(CONF_UNIQUE_ID)
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER),
    sensor_entity_id = config.get(CONF_SENSOR),
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    ac_mode = config.get(CONF_AC_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    presets = {
        key: config[value] for key, value in CONF_PRESETS.items() if value in config
    }
    fans = {
        key: config[value] for key, value in CONF_FAN.items() if value in config
    }
    
    jolly = await  hass.async_add_executor_job(jollymec, username, password, heater_id, unique_id)
    device = jolly.devices[0]

    async_add_entities([JollyMecDevice(
        name,
        heater_entity_id,
        sensor_entity_id,
        unique_id, 
        device, 
        min_temp,
        max_temp,
        target_temp,
        ac_mode,
        min_cycle_duration,
        initial_hvac_mode,
        presets,
        fans,
        )], True)

class JollyMecDevice(ClimateEntity, RestoreEntity) :
    """Representation of an Jollymec heating device."""

    def __init__(
        self, 
        name, 
        heater_entity_id,
        sensor_entity_id,
        unique_id,
        device,
        min_temp,
        max_temp,
        target_temp,
        initial_hvac_mode,
        ac_mode,
        min_cycle_duration,
        presets,
        fans,
        ):
        
        
        """Initialize the thermostat."""
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self._attr_name = name
        self._unique_id = unique_id 
        self._attr_unique_id = unique_id 
        self._device = device
        self._preset_mode = PRESET_NONE
        self._attr_native_unit_of_measurement = TEMP_CELSIUS
        # self._attr_fan_modes = None 
        # self._attr_fan_mode = None 
        self.ac_mode= ac_mode
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        #self._state= HVAC_MODE_OFF
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._temp_lock = asyncio.Lock()
        self._hvac_mode = initial_hvac_mode
        self._attr_preset_mode = PRESET_NONE
        self._active = False
        self._cur_temp = None
        self._target_temp = target_temp
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if len(presets):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_NONE] + list(presets.keys())
        else:
            self._attr_preset_modes = [PRESET_NONE]
        self._presets = presets
        if len(fans):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = [FAN_NONE] + list(fans.keys())
        else:
            self._attr_fan_modes = [FAN_NONE]
        self._fans = fans
        self._attributes = {}
        
        # _LOGGER.debug("liste des modes de puissance : %s", fans)
    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        # self.async_on_remove(
        #     async_track_state_change_event(
        #         self.hass, [self.sensor_entity_id], self._async_sensor_changed
        #     )
        # )
        # self.async_on_remove(
        #     async_track_state_change_event(
        #         self.hass, [self.heater_entity_id], self._async_switch_changed
        #     )
        # )

        # if self._keep_alive:
        #     self.async_on_remove(
        #         async_track_time_interval(
        #             self.hass, self._async_control_heating, self._keep_alive
        #         )
        #     )

        @callback
        def _async_startup(*_):
            """Init on startup."""

        if self.hass.state == CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # #Check If we have an old state
        # old_state = await self.async_get_last_state()
        # if old_state is not None:
        #     # If we have no initial temperature, restore
        #     if self._target_temp is None:
        #         # If we have a previously saved temperature
        #         if old_state.attributes.get(ATTR_TEMPERATURE) is None:
        #             if self.ac_mode:
        #                 self._target_temp = self.max_temp
        #             else:
        #                 self._target_temp = self.min_temp
        #             _LOGGER.warning(
        #                 "Undefined target temperature, falling back to %s",
        #                 self._target_temp,
        #             )
        #         else:
        #             self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
        #     if old_state.attributes.get(ATTR_PRESET_MODE) is not None:
        #         self._preset_mode = old_state.attributes.get(ATTR_PRESET_MODE)
        #     if not self._hvac_mode and old_state.state:
        #         self._hvac_mode = old_state.state
        #     for x in self.preset_modes:
        #         if old_state.attributes.get(x + "_temp") is not None:
        #              self._attributes[x + "_temp"] = old_state.attributes.get(x + "_temp")
        # else:
        # #No previous state, try and restore defaults
        #     if self._target_temp is None:
        #         if self.ac_mode:
        #             self._target_temp = self.max_temp
        #         else:
        #             self._target_temp = self.min_temp
        #     _LOGGER.warning(
        #         "No previously saved temperature, setting to %s", self._target_temp
        #     )


        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVACMode.OFF
    # @property
    # def should_poll(self):
    #     """Return the polling state."""
    #     return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_DEVICE_ALARM: self._device.alarms,
            ATTR_DEVICE_STATUS: self._device.status,
            ATTR_HUMAN_DEVICE_STATUS: self._device.status_translated,
            ATTR_SMOKE_TEMP: self._device.gas_temperature,
            ATTR_REAL_POWER: self._device.real_power,
        }


    @property
    def unique_id(self):
        """Return the unit of measurement."""
        return self._unique_id

    @property
    def name(self):
        """Return the unit of measurement."""
        return self._name

    @property
    def state(self):
        """Return the unit of measurement."""
        return self._device.status

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        #_LOGGER.debug("affichage état : %s", self._device.status)
        if self._device.status != "OFF" :
            return True
    
    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        """
        # _LOGGER.debug("affichage _hvac_mode : %s", self._hvac_mode)
        #_LOGGER.debug("affichage is_device_active : %s", self._is_device_active)
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if not self._is_device_active:
            return HVACAction.IDLE
        if self.ac_mode:
            return HVACAction.COOLING
        _LOGGER.debug("affichage HVACAction : %s", HVACAction.HEATING)
        return HVACAction.HEATING

    @property
    def fan_mode(self):
        """Return fan mode."""
        return str(self._device.current_power)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for x in range(1,5):
            fan_modes.append(str(x))
        return fan_modes
        
    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        # _LOGGER.debug("valeur de puissance choisie: %s", fan_mode)
        # if fan_mode is None or not fan_mode.isdigit():
        #     return

        try:
            self._device.set_power = int(fan_mode)
        except JollyMecError as err:
            _LOGGER.error("Failed to set fan mode, error: %s", err)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
        
    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVACMode.OFF,HVACMode.AUTO, HVACMode.HEAT]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS 

    @property
    def current_temperature(self):
        """Return the current temperature."""
        #_LOGGER.debug("valeur de temperature: %s", self._device.air_temperature)
        return self._device.air_temperature


    @property
    def gas_temperature(self):
        """Return the current temperature."""
        return self._device.smoke_temperature
        
    @property
    def preset_mode(self):
        return self._preset_mode

    @property
    def preset_modes(self):
        return [
            PRESET_NONE,
            PRESET_AWAY,
            PRESET_ECO,
            PRESET_COMFORT,
            PRESET_BOOST,
            PRESET_SLEEP,
            PRESET_ACTIVITY,
            PRESET_HOME,
        ]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature
        #Enregistrement dans la valeur des presets
        #return self._target_temp

    def update(self):
        """Get the latest data."""
        self._device.update()
        #_LOGGER.debug("retour update temp : %s", self._device.air_temperature)
        return True
    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self._device.status != 0:
            return HVACMode.HEAT
        return HVACMode.OFF


    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug("enter async")
        if hvac_mode == HVACMode.OFF:
            self._hvac_mode= HVACAction.OFF
            self.turn_off()
        elif hvac_mode == HVACMode.HEAT:
            self._hvac_mode= HVACMode.HEAT
            self.turn_on()
        self.async_write_ha_state()

    def update_temperature(self, value):
        """Update temp"""
        self._device.set_air_temperature(value)
            # if self.current_temperature != value and retrycounter < 5:
            #     retrycounter=retrycounter+1        
            #     logging.warn("Communications error, trying again (retry %s of 5)", retrycounter)
            #     time.sleep(5)
            #     self._device.set_air_temperature(value)

        #  except JollyMecError as err:
        #     _LOGGER.error("Failed to set temperature, error: %s", err)       

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._target_temp = temperature
        if self._preset_mode != PRESET_NONE:
            self._attributes[self._preset_mode + "_temp"] = self._target_temp
        self.update_temperature(temperature)
        _LOGGER.debug("set temperature %s", temperature)
        # await self._async_control_heating(force=True)
        # self.async_write_ha_state()

    def turn_on(self):
        try:
            self._device.turn_on()
        except JollyMecError as err:
            _LOGGER.error("Failed to turn on device, error: %s", err)

    def turn_off(self):
        """Turn device off."""
        try:
            self._device.turn_off()
        except JollyMecError as err:
            _LOGGER.error("Failed to turn off device, error: %s", err)

    def set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        """Test if Preset mode is valid"""
        _LOGGER.debug("mode selectionné : %s", preset_mode)
        _LOGGER.debug("puissance associée : %s", self._fans[preset_mode])
        _LOGGER.debug("temperature associée : %s", self._presets[preset_mode])
        if not preset_mode in self.preset_modes:
            return
        """if old value is preset_none we store the temp"""
        if self._preset_mode == PRESET_NONE:
            self._saved_target_temp = self._target_temp
        self._preset_mode = preset_mode
        """let's deal with the new value"""
        if self._preset_mode == PRESET_NONE:
            self._target_temp = self._saved_target_temp
        else:
            temp = self._attributes.get(self._preset_mode + "_temp", self._target_temp)
            self._target_temp = float(temp)
        self.update_temperature(self._presets[preset_mode])
        self.set_fan_mode(self._fans[preset_mode])
        #await self._async_control_heating(force=True)
        self.async_write_ha_state()       
