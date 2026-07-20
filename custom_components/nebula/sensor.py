"""Sensor platform: peer count, handshake counters, message counters, etc."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DATA_CERT_TTL,
    DATA_HANDSHAKES_INITIATED,
    DATA_HANDSHAKES_TIMED_OUT,
    DATA_MESSAGES_RX,
    DATA_MESSAGES_TX,
    DATA_PACKETS_LOST,
    DATA_PEER_COUNT,
    DATA_PENDING_HANDSHAKES,
    DATA_VERSION,
    DOMAIN,
)
from .coordinator import NebulaCoordinator
from .entity import NebulaEntity


@dataclass(frozen=True, kw_only=True)
class NebulaSensorEntityDescription(SensorEntityDescription):
    """Describes a Nebula sensor."""

    data_key: str = ""
    value_fn: Callable[[dict[str, Any]], StateType] | None = None


def _value(key: str) -> Callable[[dict[str, Any]], StateType]:
    def _fn(data: dict[str, Any]) -> StateType:
        return data.get(key)
    return _fn


SENSORS: tuple[NebulaSensorEntityDescription, ...] = (
    NebulaSensorEntityDescription(
        key="peer_count",
        translation_key="peer_count",
        data_key=DATA_PEER_COUNT,
        value_fn=_value(DATA_PEER_COUNT),
        icon="mdi:account-network",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NebulaSensorEntityDescription(
        key="pending_handshakes",
        translation_key="pending_handshakes",
        data_key=DATA_PENDING_HANDSHAKES,
        value_fn=_value(DATA_PENDING_HANDSHAKES),
        icon="mdi:handshake",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NebulaSensorEntityDescription(
        key="cert_ttl",
        translation_key="cert_ttl",
        data_key=DATA_CERT_TTL,
        value_fn=_value(DATA_CERT_TTL),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:certificate",
    ),
    NebulaSensorEntityDescription(
        key="handshakes_initiated",
        translation_key="handshakes_initiated",
        data_key=DATA_HANDSHAKES_INITIATED,
        value_fn=_value(DATA_HANDSHAKES_INITIATED),
        icon="mdi:handshake",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NebulaSensorEntityDescription(
        key="handshakes_timed_out",
        translation_key="handshakes_timed_out",
        data_key=DATA_HANDSHAKES_TIMED_OUT,
        value_fn=_value(DATA_HANDSHAKES_TIMED_OUT),
        icon="mdi:handshake-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NebulaSensorEntityDescription(
        key="messages_tx",
        translation_key="messages_tx",
        data_key=DATA_MESSAGES_TX,
        value_fn=_value(DATA_MESSAGES_TX),
        icon="mdi:upload-network-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NebulaSensorEntityDescription(
        key="messages_rx",
        translation_key="messages_rx",
        data_key=DATA_MESSAGES_RX,
        value_fn=_value(DATA_MESSAGES_RX),
        icon="mdi:download-network-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NebulaSensorEntityDescription(
        key="packets_lost",
        translation_key="packets_lost",
        data_key=DATA_PACKETS_LOST,
        value_fn=_value(DATA_PACKETS_LOST),
        icon="mdi:package-down",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NebulaSensorEntityDescription(
        key="version",
        translation_key="version",
        data_key=DATA_VERSION,
        value_fn=_value(DATA_VERSION),
        icon="mdi:tag",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nebula sensors from a config entry."""
    coordinator: NebulaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [NebulaSensor(coordinator, entry, desc) for desc in SENSORS]
    )


class NebulaSensor(NebulaEntity, SensorEntity):
    """A Nebula-derived sensor."""

    entity_description: NebulaSensorEntityDescription

    def __init__(
        self,
        coordinator: NebulaCoordinator,
        entry: ConfigEntry,
        description: NebulaSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        data: dict[str, Any] = self.coordinator.data or {}
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(data)
        return data.get(self.entity_description.data_key)
