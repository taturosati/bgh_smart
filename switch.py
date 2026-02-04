"""Switch platform for BGH Smart Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BGHDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BGH switch platform."""
    coordinator: BGHDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [BGHTurboSwitch(coordinator, entry)],
        update_before_add=True,
    )


class BGHTurboSwitch(CoordinatorEntity[BGHDataUpdateCoordinator], SwitchEntity):
    """Representation of BGH Turbo mode switch."""

    _attr_has_entity_name = True
    _attr_name = "Turbo"
    _attr_icon = "mdi:fan-speed-3"

    def __init__(
        self,
        coordinator: BGHDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_turbo"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data[CONF_NAME],
            "manufacturer": "BGH",
            "model": "Smart Control",
        }

    @property
    def is_on(self) -> bool:
        """Return true if turbo is on."""
        if self.coordinator.data:
            return self.coordinator.data.get("turbo", False)
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        # Turbo only works in cool mode (mode_raw == 1)
        mode = self.coordinator.data.get("mode_raw", 0)
        return mode == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn turbo on."""
        if not self.is_on:
            await self.coordinator.async_toggle_turbo()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn turbo off."""
        if self.is_on:
            await self.coordinator.async_toggle_turbo()
