"""Binary sensor platform for Datouboss TCP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN, PROTOCOL_QA6248
from .coordinator import DatoubossRuntimeData


@dataclass(frozen=True, kw_only=True)
class DatoubossBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any], str], bool | None]
    attributes_fn: Callable[[dict[str, Any], str], dict[str, Any] | None] | None = None
    available_fn: Callable[[dict[str, Any], str], bool] | None = None


def _qa6248_heep1_or_legacy(heep1_field: str, legacy_status_key: str) -> Callable[[dict[str, Any], str], bool | None]:
    """Для QA6248 берет живые статусы конфигурации из HSTS, для legacy — из qpigs."""
    def _fn(data: dict[str, Any], protocol: str) -> bool | None:
        if protocol == PROTOCOL_QA6248:
            hsts = data.get("hsts", {})
            if not isinstance(hsts, dict):
                return False
            flags = hsts.get("flags", {})
            
            if heep1_field == "configuration_changed":
                return flags.get("G") == "1" or flags.get("A") == "1"
            if heep1_field == "sbu_priority_flag":
                return hsts.get("mode") == "B" or flags.get("G") == "1"
            return False
            
        section = data.get("qpigs", {})
        if isinstance(section, dict):
            status = section.get(legacy_status_key)
            if isinstance(status, dict):
                return status.get(heep1_field)
        return None
    return _fn


def _qa6248_only_bool(qa6248_key: str, qa6248_field: str) -> Callable[[dict[str, Any], str], bool | None]:
    def _fn(data: dict[str, Any], protocol: str) -> bool | None:
        if protocol != PROTOCOL_QA6248:
            return None
        section = data.get(qa6248_key, {})
        return section.get(qa6248_field) if isinstance(section, dict) else None
    return _fn


BINARY_SENSORS: tuple[DatoubossBinarySensorDescription, ...] = (
    # --- Основные состояния ---
    DatoubossBinarySensorDescription(
        key="output_active",
        translation_key="output_active",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda data, proto: (
            data.get("hsts", {}).get("output_active") if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status", {}).get("output_active")
        ),
    ),
    DatoubossBinarySensorDescription(
        key="charge_active",
        translation_key="charge_active",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda data, proto: (
            data.get("hbat", {}).get("charge_active") if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status", {}).get("charge_active")
        ),
    ),
    DatoubossBinarySensorDescription(
        key="scc_charging",
        translation_key="scc_charging",
        value_fn=lambda data, proto: (
            data.get("hbat", {}).get("scc_charging") if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status", {}).get("scc_charging")
        ),
    ),
    DatoubossBinarySensorDescription(
        key="ac_charging",
        translation_key="ac_charging",
        value_fn=lambda data, proto: (
            data.get("hbat", {}).get("ac_charging") if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status", {}).get("ac_charging")
        ),
    ),

    # --- QA6248 предупреждения (из HSTS) ---
    DatoubossBinarySensorDescription(
        key="battery_disconnected",
        translation_key="battery_disconnected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "battery_disconnected"),
    ),
    DatoubossBinarySensorDescription(
        key="battery_low_alarm",
        translation_key="battery_low_alarm",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "battery_low_alarm"),
    ),
    DatoubossBinarySensorDescription(
        key="overload",
        translation_key="overload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "overload"),
    ),
    DatoubossBinarySensorDescription(
        key="overtemp",
        translation_key="overtemp",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "overtemp"),
    ),
    DatoubossBinarySensorDescription(
        key="pv_power_low",
        translation_key="pv_power_low",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:solar-power-variant-off",
        value_fn=_qa6248_only_bool("hsts", "pv_power_low"),
    ),
    DatoubossBinarySensorDescription(
        key="input_voltage_high",
        translation_key="input_voltage_high",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "input_voltage_high"),
    ),
    DatoubossBinarySensorDescription(
        key="battery_voltage_high",
        translation_key="battery_voltage_high",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "battery_voltage_high"),
    ),
    DatoubossBinarySensorDescription(
        key="fan_fault",
        translation_key="fan_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_only_bool("hsts", "fan_fault"),
    ),

    # --- Универсальные сенсоры ---
    DatoubossBinarySensorDescription(
        key="configuration_changed",
        translation_key="configuration_changed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_heep1_or_legacy("configuration_changed", "device_status"),
    ),
    DatoubossBinarySensorDescription(
        key="sbu_priority_flag",
        translation_key="sbu_priority_flag",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_heep1_or_legacy("sbu_priority_flag", "device_status"),
    ),

    # dustproof_installed читает флаг R из HSTS для QA6248
    DatoubossBinarySensorDescription(
        key="dustproof_installed",
        translation_key="dustproof_installed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: (
            data.get("hsts", {}).get("extended_flags", {}).get("R") == "1"
            if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status_2", {}).get("dustproof_installed")
        ),
    ),
    DatoubossBinarySensorDescription(
        key="switch_on",
        translation_key="switch_on",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda data, proto: (
            data.get("hsts", {}).get("extended_flags", {}).get("T") == "1"
            if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("device_status_2", {}).get("switch_on")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Datouboss binary sensors."""
    runtime: DatoubossRuntimeData = entry.runtime_data
    async_add_entities(
        DatoubossBinarySensor(runtime, entry, description)
        for description in BINARY_SENSORS
    )


class DatoubossBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Datouboss binary sensor."""

    entity_description: DatoubossBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: DatoubossRuntimeData,
        entry: ConfigEntry,
        description: DatoubossBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        protocol = self.runtime.coordinator.protocol_variant
        return self.entity_description.value_fn(self.coordinator.data, protocol)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is not None:
            protocol = self.runtime.coordinator.protocol_variant
            return self.entity_description.attributes_fn(self.coordinator.data, protocol)
        return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.available_fn is not None:
            protocol = self.runtime.coordinator.protocol_variant
            return self.entity_description.available_fn(self.coordinator.data, protocol)
        return True