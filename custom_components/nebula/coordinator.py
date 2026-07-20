"""DataUpdateCoordinator for the Nebula integration.

The coordinator owns the polling loop and the comparison between successive
scrapes needed to derive "lighthouse reachable" from a monotonically
increasing counter.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NebulaEndpointError, NebulaMetricsClient, NebulaSnapshot
from .const import (
    DATA_CERT_TTL,
    DATA_HANDSHAKES_INITIATED,
    DATA_HANDSHAKES_TIMED_OUT,
    DATA_LIGHTHOUSE_ACTIVE,
    DATA_LIGHTHOUSE_OBSERVABLE,
    DATA_MESSAGES_RX,
    DATA_MESSAGES_TX,
    DATA_PACKETS_LOST,
    DATA_PEER_COUNT,
    DATA_PENDING_HANDSHAKES,
    DATA_RAW_COUNTERS,
    DATA_RAW_METRICS,
    DATA_RUNNING,
    DATA_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class NebulaCoordinator(DataUpdateCoordinator):
    """Polls Nebula's Prometheus endpoint and derives entity state."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NebulaMetricsClient,
        name: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Nebula ({name})",
            update_interval=timedelta(seconds=max(5, int(scan_interval))),
            always_update=True,
        )
        self._client = client
        # Previous lighthouse activity counter, used to detect forward motion.
        self._prev_lighthouse_activity: float | None = None
        # The most recent successful snapshot is kept for the get_metrics
        # service and for entities that read non-rate fields directly.
        self.last_snapshot: NebulaSnapshot | None = None

    @property
    def metrics_url(self) -> str:
        return self._client.metrics_url

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = await self._client.async_fetch()
        except NebulaEndpointError as err:
            # Mark the running sensor as off; other sensors go unknown by
            # leaving the snapshot untouched (HA keeps the previous value).
            self.last_snapshot = NebulaSnapshot(running=False)
            raise UpdateFailed(str(err)) from err

        self.last_snapshot = snapshot

        lighthouse_active: bool | None
        if snapshot.lighthouse_observable:
            if self._prev_lighthouse_activity is None:
                # First observation: can't yet prove motion, treat as
                # unknown (None) so the binary_sensor reports unknown.
                lighthouse_active = None
            else:
                lighthouse_active = (
                    snapshot.lighthouse_activity > self._prev_lighthouse_activity
                )
            self._prev_lighthouse_activity = snapshot.lighthouse_activity
        else:
            # Lighthouse metrics are disabled in nebula.yml. Don't guess.
            lighthouse_active = None

        return {
            DATA_RUNNING: snapshot.running,
            DATA_LIGHTHOUSE_OBSERVABLE: snapshot.lighthouse_observable,
            DATA_LIGHTHOUSE_ACTIVE: lighthouse_active,
            DATA_PEER_COUNT: snapshot.peer_count,
            DATA_PENDING_HANDSHAKES: snapshot.pending_handshakes,
            DATA_CERT_TTL: snapshot.cert_ttl,
            DATA_HANDSHAKES_INITIATED: snapshot.handshakes_initiated,
            DATA_HANDSHAKES_TIMED_OUT: snapshot.handshakes_timed_out,
            DATA_MESSAGES_TX: snapshot.messages_tx,
            DATA_MESSAGES_RX: snapshot.messages_rx,
            DATA_PACKETS_LOST: snapshot.packets_lost,
            DATA_VERSION: snapshot.version,
            DATA_RAW_METRICS: self._raw_view(snapshot),
            DATA_RAW_COUNTERS: snapshot.counters,
        }

    @staticmethod
    def _raw_view(snapshot: NebulaSnapshot) -> dict[str, Any]:
        """Flatten raw metrics into a JSON-friendly shape for the service."""
        out: dict[str, Any] = {}
        for name, samples in snapshot.raw.items():
            if len(samples) == 1 and not samples[0].labels:
                out[name] = samples[0].value
            else:
                out[name] = [
                    {"labels": s.labels, "value": s.value} for s in samples
                ]
        return out

    def service_view(self) -> dict[str, Any]:
        """Return the latest data as a JSON-friendly dict for the service."""
        return self.data or {}

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
