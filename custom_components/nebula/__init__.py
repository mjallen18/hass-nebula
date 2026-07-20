"""The Home Assistant Nebula VPN integration.

Scrapes Nebula's Prometheus `/metrics` endpoint and exposes the result as
binary sensors (service running, lighthouse connected) and sensors (peer
count, handshake counters, message counters, cert TTL, version).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import NebulaMetricsClient
from .const import (
    CONF_METRICS_URL,
    CONF_VERIFY_TLS,
    DEFAULT_METRICS_URL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_TLS,
    DOMAIN,
    PLATFORMS,
    SERVICE_GET_METRICS,
)
from .coordinator import NebulaCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "PLATFORMS", "async_setup", "async_setup_entry", "async_unload_entry"]

# Schema for the optional `nebula.get_metrics` service. The entry_id selects
# which configured Nebula instance to query; if omitted and exactly one entry
# exists we use it automatically.
GET_METRICS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the nebula integration — registers the get_metrics service."""
    hass.data.setdefault(DOMAIN, {})

    async def _handle_get_metrics(call: ServiceCall) -> ServiceResponse:
        entry_id: str | None = call.data.get("entry_id")
        coordinators: dict[str, NebulaCoordinator] = hass.data[DOMAIN]
        if entry_id is None:
            if len(coordinators) == 1:
                entry_id = next(iter(coordinators))
            else:
                raise vol.Invalid(
                    "entry_id is required when more than one Nebula instance "
                    "is configured"
                )
        coord = coordinators.get(entry_id)
        if coord is None:
            raise vol.Invalid(f"unknown entry_id: {entry_id}")
        return {
            "running": coord.last_snapshot.running if coord.last_snapshot else False,
            "metrics": coord.service_view(),
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_METRICS,
        _handle_get_metrics,
        schema=GET_METRICS_SCHEMA,
        supports_response=True,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Nebula VPN instance from a config entry."""
    metrics_url = entry.data.get(CONF_METRICS_URL, DEFAULT_METRICS_URL)
    verify_tls = entry.data.get(CONF_VERIFY_TLS, DEFAULT_VERIFY_TLS)
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    session = async_get_clientsession(hass, verify_tls=verify_tls)
    client = NebulaMetricsClient(
        session=session, metrics_url=metrics_url, verify_tls=verify_tls
    )
    coordinator = NebulaCoordinator(
        hass=hass,
        client=client,
        name=name,
        scan_interval=scan_interval,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinators: dict[str, NebulaCoordinator] = hass.data.get(DOMAIN, {})
    coord = coordinators.pop(entry.entry_id, None)
    if coord is not None:
        await coord.async_shutdown()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options-update: reload the entry to pick up new scan interval."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up the service when the last entry is removed."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_GET_METRICS)
