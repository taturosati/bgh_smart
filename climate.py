"""Climate platform for BGH Smart Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FAN_MODES,
    FAN_MODES_REVERSE,
    MAX_TEMP,
    MIN_TEMP,
    MODES_REVERSE,
)
from .coordinator import BGHDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Map BGH modes to HA HVAC modes
HVAC_MODE_MAP = {
    "off": HVACMode.OFF,
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
    "auto": HVACMode.AUTO,
}

HVAC_MODE_REVERSE = {v: k for k, v in HVAC_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BGH climate platform."""
    coordinator: BGHDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [BGHClimate(coordinator, entry)],
        update_before_add=True,
    )


class BGHClimate(CoordinatorEntity[BGHDataUpdateCoordinator], ClimateEntity):
    """Representation of a BGH Smart AC unit."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.AUTO,
    ]
    _attr_fan_modes = list(FAN_MODES.values())
    _attr_swing_modes = [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]

    def __init__(
        self,
        coordinator: BGHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data[CONF_NAME],
            "manufacturer": "BGH",
            "model": "Smart Control",
        }
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data:
            return self.coordinator.data.get("current_temperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data:
            return self.coordinator.data.get("target_temperature")
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if self.coordinator.data:
            mode = self.coordinator.data.get("mode", "off")
            return HVAC_MODE_MAP.get(mode, HVACMode.OFF)
        return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self.coordinator.data:
            fan_speed = self.coordinator.data.get("fan_speed", 1)
            return FAN_MODES.get(fan_speed, "low")
        return None

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        if self.coordinator.data:
            swing_h = self.coordinator.data.get("swing_horizontal", False)
            swing_v = self.coordinator.data.get("swing_vertical", False)
            if swing_h and swing_v:
                return SWING_BOTH
            elif swing_h:
                return SWING_HORIZONTAL
            elif swing_v:
                return SWING_VERTICAL
        return SWING_OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.coordinator.data:
            return {
                "turbo": self.coordinator.data.get("turbo", False),
            }
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.error("No temperature provided")
            return

        await self.coordinator.async_set_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        bgh_mode = HVAC_MODE_REVERSE.get(hvac_mode)
        if bgh_mode is None:
            _LOGGER.error("Invalid HVAC mode: %s", hvac_mode)
            return

        mode_value = MODES_REVERSE.get(bgh_mode)
        if mode_value is None:
            _LOGGER.error("Cannot map mode: %s", bgh_mode)
            return

        # Keep current fan speed if available
        current_fan = None
        if self.coordinator.data:
            current_fan = self.coordinator.data.get("fan_speed")

        await self.coordinator.async_set_mode(mode_value, current_fan)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        fan_value = FAN_MODES_REVERSE.get(fan_mode)
        if fan_value is None:
            _LOGGER.error("Invalid fan mode: %s", fan_mode)
            return

        # Keep current mode
        current_mode = None
        if self.coordinator.data:
            current_mode = self.coordinator.data.get("mode_raw", 0)

        await self.coordinator.async_set_mode(current_mode, fan_value)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        current_h = self.coordinator.data.get("swing_horizontal", False) if self.coordinator.data else False
        current_v = self.coordinator.data.get("swing_vertical", False) if self.coordinator.data else False

        target_h = swing_mode in (SWING_HORIZONTAL, SWING_BOTH)
        target_v = swing_mode in (SWING_VERTICAL, SWING_BOTH)

        # Toggle horizontal if needed
        if target_h != current_h:
            await self.coordinator.async_toggle_swing_horizontal()

        # Toggle vertical if needed
        if target_v != current_v:
            await self.coordinator.async_toggle_swing_vertical()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Default to cooling mode when turning on
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
