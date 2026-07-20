"""Shared base entity for the Nebula VPN integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NebulaCoordinator


def make_device_info(entry: ConfigEntry, coordinator: NebulaCoordinator) -> DeviceInfo:
    """Build a DeviceInfo block shared by every entity under this entry."""
    name = entry.data.get(CONF_NAME, "Nebula")
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=name,
        manufacturer="Slack",
        model="Nebula",
        sw_version=coordinator.data.get("version") if coordinator.data else None,
        configuration_url=coordinator.metrics_url,
    )


class NebulaEntity(CoordinatorEntity[NebulaCoordinator]):
    """Common base: wires coordinator + device info + available flag."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NebulaCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = make_device_info(entry, coordinator)

    @property
    def available(self) -> bool:
        """Available only when the most recent scrape succeeded."""
        snap = self.coordinator.last_snapshot
        return snap is not None and snap.running
