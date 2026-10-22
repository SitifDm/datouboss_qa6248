"""Sensor platform for Datouboss TCP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN, PROTOCOL_QA6248
from .coordinator import DatoubossRuntimeData


@dataclass(frozen=True, kw_only=True)
class DatoubossSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any], str], Any]
    attributes_fn: Callable[[dict[str, Any], str], dict[str, Any] | None] | None = None
    available_fn: Callable[[dict[str, Any], str], bool] | None = None


def _qa6248_or_legacy(qa6248_key: str, qa6248_field: str, legacy_key: str, legacy_field: str) -> Callable[[dict[str, Any], str], Any]:
    """Return a value_fn that works for both protocols."""
    def _fn(data: dict[str, Any], protocol: str) -> Any:
        if protocol == PROTOCOL_QA6248:
            section = data.get(qa6248_key, {})
            return section.get(qa6248_field) if isinstance(section, dict) else None
        section = data.get(legacy_key, {})
        return section.get(legacy_field) if isinstance(section, dict) else None
    return _fn


def _qa6248_only(qa6248_key: str, qa6248_field: str) -> Callable[[dict[str, Any], str], Any]:
    """Return a value_fn that works only for QA6248."""
    def _fn(data: dict[str, Any], protocol: str) -> Any:
        if protocol != PROTOCOL_QA6248:
            return None
        section = data.get(qa6248_key, {})
        return section.get(qa6248_field) if isinstance(section, dict) else None
    return _fn


def _qa6248_available(qa6248_key: str) -> Callable[[dict[str, Any], str], bool]:
    """Return an available_fn that is True only for QA6248."""
    def _fn(data: dict[str, Any], protocol: str) -> bool:
        return protocol == PROTOCOL_QA6248 and qa6248_key in data
    return _fn


SENSORS: tuple[DatoubossSensorDescription, ...] = (
    # --- Режим работы ---
    DatoubossSensorDescription(
        key="mode",
        translation_key="mode",
        icon="mdi:transmission-tower",
        value_fn=_qa6248_or_legacy("hsts", "mode_name", "qmod", "state"),
        attributes_fn=lambda data, proto: {
            "code": data.get("hsts", {}).get("mode") if proto == PROTOCOL_QA6248 else data.get("qmod", {}).get("code"),
        },
    ),

    # --- Серийный номер ---
    DatoubossSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:identifier",
        value_fn=lambda data, proto: data.get("qid") or data.get("serial"),
    ),

    # --- Напряжения ---
    DatoubossSensorDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hgrid", "grid_voltage", "qpigs", "grid_voltage"),
    ),
    DatoubossSensorDescription(
        key="output_voltage",
        translation_key="output_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hop", "output_voltage", "qpigs", "output_voltage"),
    ),
    DatoubossSensorDescription(
        key="bus_voltage",
        translation_key="bus_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hbat", "bus_voltage", "qpigs", "bus_voltage"),
    ),
    DatoubossSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hbat", "battery_voltage", "qpigs", "battery_voltage"),
    ),

    # --- Частоты ---
    DatoubossSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hgrid", "grid_frequency", "qpigs", "grid_frequency"),
    ),
    DatoubossSensorDescription(
        key="output_frequency",
        translation_key="output_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hop", "output_frequency", "qpigs", "output_frequency"),
    ),

    # --- Мощности ---
    DatoubossSensorDescription(
        key="output_apparent_power",
        translation_key="output_apparent_power",
        native_unit_of_measurement="VA",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=_qa6248_or_legacy("hop", "apparent_power", "qpigs", "output_apparent_power"),
    ),
    DatoubossSensorDescription(
        key="output_active_power",
        translation_key="output_active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hop", "active_power", "qpigs", "output_active_power"),
    ),
    DatoubossSensorDescription(
        key="load_percent",
        translation_key="load_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        value_fn=_qa6248_or_legacy("hop", "load_percent", "qpigs", "load_percent"),
    ),

    # --- PV данные ---
    DatoubossSensorDescription(
        key="pv_output_power",
        translation_key="pv_output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hpv", "pv_power", "qpigs", "pv_output_power"),
    ),
    DatoubossSensorDescription(
        key="pv_input_voltage",
        translation_key="pv_input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hpv", "pv_voltage", "qpigs", "pv_input_voltage"),
    ),
    DatoubossSensorDescription(
        key="pv_current",
        translation_key="pv_battery_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hpv", "pv_current", "qpigs", "pv_battery_current"),
    ),

    # --- Батарея ---
    DatoubossSensorDescription(
        key="battery_charging_current",
        translation_key="battery_charging_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hbat", "charge_current", "qpigs", "battery_charging_current"),
    ),
    DatoubossSensorDescription(
        key="battery_discharge_current",
        translation_key="battery_discharge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("hbat", "discharge_current", "qpigs", "battery_discharge_current"),
    ),
    DatoubossSensorDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-medium",
        value_fn=_qa6248_or_legacy("hbat", "battery_capacity", "qpigs", "battery_capacity"),
    ),
    DatoubossSensorDescription(
        key="scc_battery_voltage",
        translation_key="scc_battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, proto: (
            data.get("hpvb", {}).get("scc_battery_voltage")
            if proto == PROTOCOL_QA6248
            else data.get("qpigs", {}).get("scc_battery_voltage")
        ),
    ),

    # --- Температуры ---
    DatoubossSensorDescription(
        key="heatsink_temperature",
        translation_key="heatsink_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_or_legacy("htemp", "inverter_temperature", "qpigs", "heatsink_temperature"),
    ),
    DatoubossSensorDescription(
        key="pv_temperature",
        translation_key="pv_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_only("htemp", "pv_temperature"),
        available_fn=_qa6248_available("htemp"),
    ),
    DatoubossSensorDescription(
        key="boost_temperature",
        translation_key="boost_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_only("htemp", "boost_temperature"),
        available_fn=_qa6248_available("htemp"),
    ),
    DatoubossSensorDescription(
        key="max_temperature",
        translation_key="max_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_qa6248_only("htemp", "max_temperature"),
        available_fn=_qa6248_available("htemp"),
    ),

    # --- Счётчики энергии (только QA6248) ---
    DatoubossSensorDescription(
        key="daily_energy",
        translation_key="daily_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power",
        value_fn=_qa6248_only("hgen", "daily_energy"),
        available_fn=_qa6248_available("hgen"),
    ),
    DatoubossSensorDescription(
        key="monthly_energy",
        translation_key="monthly_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:calendar-month",
        value_fn=_qa6248_only("hgen", "monthly_energy"),
        available_fn=_qa6248_available("hgen"),
    ),
    DatoubossSensorDescription(
        key="yearly_energy",
        translation_key="yearly_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:calendar-clock",
        value_fn=_qa6248_only("hgen", "yearly_energy"),
        available_fn=_qa6248_available("hgen"),
    ),
    DatoubossSensorDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=_qa6248_only("hgen", "total_energy"),
        available_fn=_qa6248_available("hgen"),
    ),

    # --- Настройки из HEEP1 (только QA6248) ---
    DatoubossSensorDescription(
        key="battery_bulk_voltage",
        translation_key="battery_bulk_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_or_legacy("heep1", "bulk_voltage", "qpiri", "battery_bulk_voltage"),
    ),
    DatoubossSensorDescription(
        key="battery_float_voltage",
        translation_key="battery_float_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_or_legacy("heep1", "float_voltage", "qpiri", "battery_float_voltage"),
    ),
    DatoubossSensorDescription(
        key="battery_under_voltage",
        translation_key="battery_under_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_or_legacy("heep1", "low_voltage_cutoff", "qpiri", "battery_under_voltage"),
    ),
    DatoubossSensorDescription(
        key="battery_type",
        translation_key="battery_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-cog",
        value_fn=_qa6248_or_legacy("heep1", "battery_type_name", "qpiri", "battery_type"),
        attributes_fn=lambda data, proto: {
            "code": data.get("heep1", {}).get("battery_type_code") if proto == PROTOCOL_QA6248 else data.get("qpiri", {}).get("battery_type_code"),
        },
    ),
    DatoubossSensorDescription(
        key="max_total_charge_current",
        translation_key="max_total_charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_or_legacy("heep1", "max_total_charge_current", "qpiri", "max_total_charge_current"),
    ),
    DatoubossSensorDescription(
        key="max_ac_charge_current",
        translation_key="max_ac_charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_qa6248_or_legacy("heep1", "max_ac_charge_current", "qpiri", "max_ac_charge_current"),
    ),

    # --- Legacy-only сенсоры (device_status_bits, warnings и т.д.) ---
    DatoubossSensorDescription(
        key="device_status_bits",
        translation_key="device_status_bits",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:dip-switch",
        value_fn=lambda data, proto: data.get("qpigs", {}).get("device_status_bits") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: data.get("qpigs", {}).get("device_status") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="device_status_bits_2",
        translation_key="device_status_bits_2",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:dip-switch",
        value_fn=lambda data, proto: data.get("qpigs", {}).get("device_status_bits_2") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: data.get("qpigs", {}).get("device_status_2") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="warnings_bitfield",
        translation_key="warnings_bitfield",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-outline",
        value_fn=lambda data, proto: data.get("qpiws", {}).get("bitfield") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: {
            "active_indexes": data.get("qpiws", {}).get("active_indexes", []),
        } if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="fan_offset",
        translation_key="fan_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:fan",
        value_fn=lambda data, proto: data.get("qpigs", {}).get("fan_offset") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="eeprom_version",
        translation_key="eeprom_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chip",
        value_fn=lambda data, proto: data.get("qpigs", {}).get("eeprom_version") if proto != PROTOCOL_QA6248 else None,
    ),

    # --- Legacy-only рейтинговые значения из QPIRI ---
    DatoubossSensorDescription(
        key="grid_rating_voltage",
        translation_key="grid_rating_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("grid_rating_voltage") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="grid_rating_current",
        translation_key="grid_rating_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("grid_rating_current") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="ac_output_rating_voltage",
        translation_key="ac_output_rating_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("ac_output_rating_voltage") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="ac_output_rating_frequency",
        translation_key="ac_output_rating_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("ac_output_rating_frequency") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="ac_output_rating_current",
        translation_key="ac_output_rating_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("ac_output_rating_current") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="ac_output_rating_apparent_power",
        translation_key="ac_output_rating_apparent_power",
        native_unit_of_measurement="VA",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:flash",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("ac_output_rating_apparent_power") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="ac_output_rating_active_power",
        translation_key="ac_output_rating_active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("ac_output_rating_active_power") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="battery_rating_voltage",
        translation_key="battery_rating_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("battery_rating_voltage") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="battery_recharge_voltage",
        translation_key="battery_recharge_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("battery_recharge_voltage") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="battery_redischarge_voltage",
        translation_key="battery_redischarge_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, proto: data.get("qpiri", {}).get("battery_redischarge_voltage") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="parallel_max_num",
        translation_key="parallel_max_num",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:call-split",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("parallel_max_num") if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="machine_type",
        translation_key="machine_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:identifier",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("machine_type") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: {
            "code": data.get("qpiri", {}).get("machine_type_code"),
        } if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="topology",
        translation_key="topology",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:sitemap",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("topology") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: {
            "code": data.get("qpiri", {}).get("topology_code"),
        } if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="output_mode",
        translation_key="output_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:export",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("output_mode") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: {
            "code": data.get("qpiri", {}).get("output_mode_code"),
        } if proto != PROTOCOL_QA6248 else None,
    ),
    DatoubossSensorDescription(
        key="pv_ok_condition",
        translation_key="pv_ok_condition",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:solar-power-variant",
        value_fn=lambda data, proto: data.get("qpiri", {}).get("pv_ok_condition") if proto != PROTOCOL_QA6248 else None,
        attributes_fn=lambda data, proto: {
            "code": data.get("qpiri", {}).get("pv_ok_condition_code"),
        } if proto != PROTOCOL_QA6248 else None,
    ),

    # --- Raw payloads (для отладки) ---
    DatoubossSensorDescription(
        key="raw_payloads",
        translation_key="raw_payloads",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:code-json",
        value_fn=lambda data, proto: len(data.get("raw", {})),
        attributes_fn=lambda data, proto: data.get("raw", {}),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Datouboss sensors."""
    runtime: DatoubossRuntimeData = entry.runtime_data
    async_add_entities(
        DatoubossSensor(runtime, entry, description) for description in SENSORS
    )


class DatoubossSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Datouboss sensor."""

    entity_description: DatoubossSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: DatoubossRuntimeData,
        entry: ConfigEntry,
        description: DatoubossSensorDescription,
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
    def native_value(self) -> Any:
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