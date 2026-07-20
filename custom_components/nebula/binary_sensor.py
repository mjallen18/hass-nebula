"""Binary sensor platform: service running, lighthouse connected."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DATA_LIGHTHOUSE_ACTIVE,
    DATA_LIGHTHOUSE_OBSERVABLE,
    DATA_RUNNING,
    DOMAIN,
)
from .coordinator import NebulaCoordinator
from .entity import NebulaEntity


@dataclass(frozen=True, kw_only=True)
class NebulaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Nebula binary sensor."""

    data_key: str = ""


RUNNING = NebulaBinarySensorEntityDescription(
    key="running",
    translation_key="running",
    data_key=DATA_RUNNING,
    icon="mdi:vpn",
)

LIGHTHOUSE = NebulaBinarySensorEntityDescription(
    key="lighthouse_connected",
    translation_key="lighthouse_connected",
    data_key=DATA_LIGHTHOUSE_ACTIVE,
    icon="mdi:lightbulb",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nebula binary sensors from a config entry."""
    coordinator: NebulaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NebulaBinarySensor(coordinator, entry, RUNNING),
            NebulaBinarySensor(coordinator, entry, LIGHTHOUSE),
        ]
    )


class NebulaBinarySensor(NebulaEntity, BinarySensorEntity):
    """A Nebula-derived binary sensor."""

    entity_description: NebulaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NebulaCoordinator,
        entry: ConfigEntry,
        description: NebulaBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data: dict[str, Any] = self.coordinator.data or {}
        if self.entity_description.key == "lighthouse_connected":
            # When lighthouse metrics aren't enabled we can't determine this;
            # report unknown (None) instead of guessing.
            if not data.get(DATA_LIGHTHOUSE_OBSERVABLE, False):
                return None
            return data.get(DATA_LIGHTHOUSE_ACTIVE)
        return data.get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: dict[str, Any] = self.coordinator.data or {}
        if self.entity_description.key == "lighthouse_connected":
            return {
                "observable": data.get(DATA_LIGHTHOUSE_OBSERVABLE, False),
            }
        return {}
