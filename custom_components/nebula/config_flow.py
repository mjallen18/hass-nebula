"""Config flow for the Nebula VPN integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import NebulaAuthError, NebulaEndpointError, NebulaMetricsClient
from .const import (
    CONF_METRICS_URL,
    CONF_VERIFY_TLS,
    DEFAULT_METRICS_URL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_TLS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_METRICS_URL, default=DEFAULT_METRICS_URL): str,
        vol.Optional(CONF_VERIFY_TLS, default=DEFAULT_VERIFY_TLS): bool,
    }
)


async def _validate_metrics(
    hass: HomeAssistant, metrics_url: str, verify_tls: bool
) -> None:
    """Probe the metrics endpoint during config flow.

    Raises CannotConnect on network/parse failure, InvalidAuth on 401/403.
    """
    session = async_get_clientsession(hass, verify_ssl=verify_tls)
    client = NebulaMetricsClient(
        session=session, metrics_url=metrics_url, verify_tls=verify_tls
    )
    try:
        snapshot = await client.async_fetch()
    except NebulaAuthError as err:
        raise InvalidAuth(str(err)) from err
    except NebulaEndpointError as err:
        raise CannotConnect(str(err)) from err
    if not snapshot.running:
        raise CannotConnect(
            f"endpoint responded but exposed no metrics; check {metrics_url}"
        )


class NebulaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nebula VPN."""

    VERSION = 1

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "NebulaOptionsFlowHandler":
        """Wire up the options flow so users can change scan interval."""
        return NebulaOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: ask for the metrics URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_metrics(
                    self.hass,
                    user_input[CONF_METRICS_URL],
                    user_input[CONF_VERIFY_TLS],
                )
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.debug("Cannot connect to nebula metrics: %s", err)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as err:  # pragma: no cover - defensive
                _LOGGER.exception("Unexpected error validating nebula endpoint")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_METRICS_URL], raise_on_update=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_METRICS_URL: user_input[CONF_METRICS_URL],
                        CONF_VERIFY_TLS: user_input[CONF_VERIFY_TLS],
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class NebulaOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow: change scan interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Unable to reach the Nebula metrics endpoint."""


class InvalidAuth(HomeAssistantError):
    """The Nebula metrics endpoint rejected our request."""
