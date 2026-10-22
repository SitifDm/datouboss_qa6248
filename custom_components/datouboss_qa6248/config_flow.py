"""Config flow for Datouboss TCP."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .client import DatoubossError, DatoubossTcpClient
from .client_serial import DatoubossSerialClient
from .const import (
    BAUDRATE_OPTIONS,
    CONF_BAUDRATE,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SERIAL_DEVICE,
    CONF_TIMEOUT,
    CONF_TRANSPORT,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERIAL_DEVICE,
    DEFAULT_TIMEOUT,
    DEFAULT_TRANSPORT,
    DOMAIN,
    PROTOCOL_AUTO,
    PROTOCOL_CLASSIC,
    PROTOCOL_QA6248,
    PROTOCOL_VMII,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1,
        max=60,
        step=1,
        mode=selector.NumberSelectorMode.SLIDER,
        unit_of_measurement="s",
    )
)

SCAN_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=2,
        max=3600,
        step=1,
        mode=selector.NumberSelectorMode.SLIDER,
        unit_of_measurement="s",
    )
)

PROTOCOL_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            PROTOCOL_AUTO,
            PROTOCOL_CLASSIC,
            PROTOCOL_VMII,
            PROTOCOL_QA6248,  # <-- Добавлено
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="protocol_variant",
    )
)

TRANSPORT_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[TRANSPORT_TCP, TRANSPORT_SERIAL],
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="transport",
    )
)

SERIAL_DEVICE_SELECTOR = selector.TextSelector()

BAUDRATE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[str(baud) for baud in BAUDRATE_OPTIONS],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _build_probe_client(user_input: dict[str, Any]):
    """Build a probe client for the chosen transport."""
    transport = user_input.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
    if transport == TRANSPORT_SERIAL:
        return DatoubossSerialClient(
            device=user_input.get(CONF_SERIAL_DEVICE, DEFAULT_SERIAL_DEVICE),
            baudrate=int(user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)),
            timeout=int(user_input[CONF_TIMEOUT]),
            protocol_variant=user_input[CONF_PROTOCOL],
        )
    return DatoubossTcpClient(
        user_input.get(CONF_HOST, "127.0.0.1"),
        int(user_input.get(CONF_PORT, DEFAULT_PORT)),
        int(user_input[CONF_TIMEOUT]),
        protocol_variant=user_input[CONF_PROTOCOL],
    )


def _fallback_id(user_input: dict[str, Any]) -> str:
    if user_input.get(CONF_TRANSPORT, DEFAULT_TRANSPORT) == TRANSPORT_SERIAL:
        return str(user_input.get(CONF_SERIAL_DEVICE, DEFAULT_SERIAL_DEVICE))
    return f"{user_input.get(CONF_HOST)}:{user_input.get(CONF_PORT)}"


async def _probe_client(user_input: dict[str, Any]) -> dict[str, Any]:
    """Probe the inverter and always release the transport afterwards."""
    client = _build_probe_client(user_input)
    try:
        return await client.probe()
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            await close()


def _base_fields() -> dict[Any, Any]:
    return {
        vol.Required(CONF_TRANSPORT, default=DEFAULT_TRANSPORT): TRANSPORT_SELECTOR,
        vol.Optional(CONF_HOST, default="127.0.0.1"): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_SERIAL_DEVICE, default=DEFAULT_SERIAL_DEVICE): SERIAL_DEVICE_SELECTOR,
        vol.Optional(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): BAUDRATE_SELECTOR,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): SCAN_INTERVAL_SELECTOR,
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): TIMEOUT_SELECTOR,
        vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): PROTOCOL_SELECTOR,
    }


class DatoubossConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Datouboss TCP."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_BAUDRATE] = int(
                user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            )
            try:
                probe = await _probe_client(user_input)
                serial = probe["serial"] or _fallback_id(user_input)
            except DatoubossError:
                _LOGGER.debug("Datouboss probe failed", exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                data = {
                    **user_input,
                    CONF_SERIAL: serial,
                }
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    **_base_fields(),
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "DatoubossOptionsFlow":
        return DatoubossOptionsFlow()


class DatoubossOptionsFlow(config_entries.OptionsFlowWithReload):
    """Datouboss options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_BAUDRATE] = int(
                user_input.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            )
            try:
                await _probe_client(user_input)
            except DatoubossError:
                _LOGGER.debug("Datouboss options probe failed", exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(data=user_input)
        options_schema = vol.Schema(_base_fields())
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                {
                    CONF_TRANSPORT: self.config_entry.options.get(
                        CONF_TRANSPORT,
                        self.config_entry.data.get(CONF_TRANSPORT, DEFAULT_TRANSPORT),
                    ),
                    CONF_HOST: self.config_entry.options.get(
                        CONF_HOST,
                        self.config_entry.data[CONF_HOST],
                    ),
                    CONF_PORT: self.config_entry.options.get(
                        CONF_PORT,
                        self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ),
                    CONF_SERIAL_DEVICE: self.config_entry.options.get(
                        CONF_SERIAL_DEVICE,
                        self.config_entry.data.get(CONF_SERIAL_DEVICE, DEFAULT_SERIAL_DEVICE),
                    ),
                    CONF_BAUDRATE: str(
                        self.config_entry.options.get(
                            CONF_BAUDRATE,
                            self.config_entry.data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                        )
                    ),
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                    CONF_TIMEOUT: self.config_entry.options.get(
                        CONF_TIMEOUT,
                        self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ),
                    CONF_PROTOCOL: self.config_entry.options.get(
                        CONF_PROTOCOL,
                        self.config_entry.data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
                    ),
                },
            ),
            errors=errors,
        )