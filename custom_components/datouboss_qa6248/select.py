"""Select platform for Datouboss TCP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AC_INPUT_RANGE_MAP,
    AC_INPUT_RANGE_REVERSE,
    CONF_SERIAL,
    DOMAIN,
    PROTOCOL_QA6248,
    QA6248_AC_INPUT_RANGE_MAP,
    QA6248_AC_INPUT_RANGE_REVERSE,
    QA6248_CHARGER_PRIORITY_MAP,
    QA6248_CHARGER_PRIORITY_REVERSE,
    QA6248_OUTPUT_PRIORITY_MAP,
    QA6248_OUTPUT_PRIORITY_REVERSE,
)
from .coordinator import DatoubossRuntimeData


@dataclass(frozen=True, kw_only=True)
class DatoubossSelectDescription(SelectEntityDescription):
    current_option_fn: Callable[[Any], str | None]
    command_fn: Callable[[Any, str], str]
    options_fn: Callable[[Any], list[str]]
    attributes_fn: Callable[[Any], dict[str, Any] | None] | None = None
    available_fn: Callable[[Any], bool] | None = None


def _get_current_option(
    data: dict[str, Any],
    qa6248_key: str,
    qa6248_field: str,
    legacy_key: str,
    legacy_field: str,
    protocol: str,
) -> str | None:
    """Get current option from either QA6248 or legacy data."""
    if protocol == PROTOCOL_QA6248:
        section = data.get(qa6248_key, {})
        if isinstance(section, dict):
            return section.get(qa6248_field)
    section = data.get(legacy_key, {})
    if isinstance(section, dict):
        return section.get(legacy_field)
    return None


def _get_options_with_current(
    options: list[str], current: str | None
) -> list[str]:
    """Return options list, appending current if not already present."""
    if current is None or current in options:
        return options
    return [*options, current]


SELECTS: tuple[DatoubossSelectDescription, ...] = (
    # --- Output source priority ---
    DatoubossSelectDescription(
        key="output_source_priority",
        translation_key="output_source_priority",
        current_option_fn=lambda coordinator: _get_current_option(
            coordinator.data,
            "heep1", "output_source_priority_name",  # ← ИСПРАВЛЕНО: было work_mode_name
            "qpiri", "output_source_priority",
            coordinator.protocol_variant,
        ),
        command_fn=lambda coordinator, option: coordinator.build_output_source_priority_command(option),
        options_fn=lambda coordinator: _get_options_with_current(
            coordinator.get_writable_output_source_priority_options(),
            coordinator.data.get("heep1", {}).get("output_source_priority_name")
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else coordinator.data.get("qpiri", {}).get("output_source_priority"),
        ),
        attributes_fn=lambda coordinator: {
            "code": (
                coordinator.data.get("heep1", {}).get("output_source_priority")
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else coordinator.data.get("qpiri", {}).get("output_source_priority_code")
            ),
            "writable_options": coordinator.get_writable_output_source_priority_options(),
            "protocol_variant": coordinator.protocol_variant,
        },
    ),

    # --- Charger source priority ---
    DatoubossSelectDescription(
        key="charger_source_priority",
        translation_key="charger_source_priority",
        current_option_fn=lambda coordinator: _get_current_option(
            coordinator.data,
            "heep1", "charger_source_priority_name",  # ← ИСПРАВЛЕНО: было charge_priority_name
            "qpiri", "charger_source_priority",
            coordinator.protocol_variant,
        ),
        command_fn=lambda coordinator, option: coordinator.build_charger_source_priority_command(option),
        options_fn=lambda coordinator: _get_options_with_current(
            coordinator.get_writable_charger_source_priority_options(),
            coordinator.data.get("heep1", {}).get("charger_source_priority_name")
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else coordinator.data.get("qpiri", {}).get("charger_source_priority"),
        ),
        attributes_fn=lambda coordinator: {
            "code": (
                coordinator.data.get("heep1", {}).get("charger_source_priority")
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else coordinator.data.get("qpiri", {}).get("charger_source_priority_code")
            ),
            "writable_options": coordinator.get_writable_charger_source_priority_options(),
            "protocol_variant": coordinator.protocol_variant,
        },
    ),

    # --- AC input range ---
    DatoubossSelectDescription(
        key="ac_input_range",
        translation_key="ac_input_range",
        current_option_fn=lambda coordinator: _get_current_option(
            coordinator.data,
            "heep1", "ac_input_range_name",
            "qpiri", "ac_input_range",
            coordinator.protocol_variant,
        ),
        command_fn=lambda coordinator, option: coordinator.build_ac_input_range_command(option),
        options_fn=lambda coordinator: _get_options_with_current(
            list(QA6248_AC_INPUT_RANGE_MAP.keys())
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else list(AC_INPUT_RANGE_MAP.keys()),
            coordinator.data.get("heep1", {}).get("ac_input_range_name")
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else coordinator.data.get("qpiri", {}).get("ac_input_range"),
        ),
        attributes_fn=lambda coordinator: {
            "code": (
                coordinator.data.get("heep1", {}).get("ac_input_range")
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else coordinator.data.get("qpiri", {}).get("ac_input_range_code")
            ),
            "writable_options": (
                list(QA6248_AC_INPUT_RANGE_MAP.keys())
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else list(AC_INPUT_RANGE_MAP.keys())
            ),
            "protocol_variant": coordinator.protocol_variant,
        },
    ),

    # --- Max AC charge current ---
    DatoubossSelectDescription(
        key="max_ac_charge_current",
        translation_key="max_ac_charge_current",
        current_option_fn=lambda coordinator: _format_value_with_unit(
            coordinator.data.get("heep1", {}).get("max_ac_charge_current")
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else coordinator.data.get("qpiri", {}).get("max_ac_charge_current"),
            "A",
        ),
        command_fn=lambda coordinator, option: coordinator.build_max_ac_charge_current_command(
            _parse_numeric_option(option)
        ),
        options_fn=lambda coordinator: _get_options_with_current(
            [
                f"{value} A"
                for value in (
                    coordinator.supported_ac_charge_currents
                    or [2, 10, 20, 30, 40, 50, 60]
                )
            ],
            _format_value_with_unit(
                coordinator.data.get("heep1", {}).get("max_ac_charge_current")
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else coordinator.data.get("qpiri", {}).get("max_ac_charge_current"),
                "A",
            ),
        ),
        attributes_fn=lambda coordinator: {
            "supported_values": coordinator.supported_ac_charge_currents
            or [2, 10, 20, 30, 40, 50, 60],
            "writable_options": [
                f"{value} A"
                for value in (
                    coordinator.supported_ac_charge_currents
                    or [2, 10, 20, 30, 40, 50, 60]
                )
            ],
            "protocol_variant": coordinator.protocol_variant,
        },
    ),

    # --- Max total charge current ---
    DatoubossSelectDescription(
        key="max_total_charge_current",
        translation_key="max_total_charge_current",
        current_option_fn=lambda coordinator: _format_value_with_unit(
            coordinator.data.get("heep1", {}).get("max_total_charge_current")
            if coordinator.protocol_variant == PROTOCOL_QA6248
            else coordinator.data.get("qpiri", {}).get("max_total_charge_current"),
            "A",
        ),
        command_fn=lambda coordinator, option: coordinator.build_max_total_charge_current_command(
            _parse_numeric_option(option)
        ),
        options_fn=lambda coordinator: _get_options_with_current(
            [
                f"{value} A"
                for value in (
                    coordinator.supported_total_charge_currents
                    or [10, 20, 30, 40, 50, 60, 80, 100]
                )
            ],
            _format_value_with_unit(
                coordinator.data.get("heep1", {}).get("max_total_charge_current")
                if coordinator.protocol_variant == PROTOCOL_QA6248
                else coordinator.data.get("qpiri", {}).get("max_total_charge_current"),
                "A",
            ),
        ),
        attributes_fn=lambda coordinator: {
            "supported_values": coordinator.supported_total_charge_currents
            or [10, 20, 30, 40, 50, 60, 80, 100],
            "writable_options": [
                f"{value} A"
                for value in (
                    coordinator.supported_total_charge_currents
                    or [10, 20, 30, 40, 50, 60, 80, 100]
                )
            ],
            "protocol_variant": coordinator.protocol_variant,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Datouboss selects."""
    runtime: DatoubossRuntimeData = entry.runtime_data
    async_add_entities(
        DatoubossSelect(runtime, entry, description) for description in SELECTS
    )


class DatoubossSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Datouboss writable select."""

    entity_description: DatoubossSelectDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: DatoubossRuntimeData,
        entry: ConfigEntry,
        description: DatoubossSelectDescription,
    ) -> None:
        super().__init__(runtime.coordinator)
        self.runtime = runtime
        self.entity_description = description
        serial = entry.data.get(CONF_SERIAL, entry.entry_id)
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Datouboss",
            model=runtime.coordinator.model_name or "Voltronic-compatible inverter",
            name=entry.title,
            serial_number=entry.data.get(CONF_SERIAL),
        )

    @property
    def current_option(self) -> str | None:
        value = self.entity_description.current_option_fn(self.coordinator)
        if value is None:
            return None
        return str(value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._sync_registry_capabilities()

    @property
    def options(self) -> list[str]:
        return self.entity_description.options_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is not None:
            return self.entity_description.attributes_fn(self.coordinator)
        return None

    @property
    def available(self) -> bool:
        if self.entity_description.available_fn is None:
            return super().available
        return super().available and self.entity_description.available_fn(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        attributes = self.extra_state_attributes or {}
        writable_options = attributes.get("writable_options")
        if writable_options is not None and option not in writable_options:
            raise ValueError(f"Option '{option}' is read-only for this inverter")
        await self.runtime.coordinator.async_send_write_command(
            self.entity_description.command_fn(self.runtime.coordinator, option)
        )

    def _handle_coordinator_update(self) -> None:
        self._sync_registry_capabilities()
        super()._handle_coordinator_update()

    def _sync_registry_capabilities(self) -> None:
        if self.hass is None or self.entity_id is None:
            return
        registry = er.async_get(self.hass)
        if (entry := registry.async_get(self.entity_id)) is None:
            return
        capabilities = self.capability_attributes
        if entry.capabilities == capabilities:
            return
        registry.async_update_entity(self.entity_id, capabilities=capabilities)


def _format_integerish_option(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def _format_value_with_unit(value: Any, unit: str) -> str | None:
    formatted = _format_integerish_option(value)
    if formatted is None:
        return None
    return f"{formatted} {unit}"


def _parse_numeric_option(option: str) -> int:
    return int(float(option.split()[0]))