"""Number platform for Datouboss TCP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN, PROTOCOL_QA6248
from .coordinator import DatoubossRuntimeData


@dataclass(frozen=True, kw_only=True)
class DatoubossNumberDescription(NumberEntityDescription):
    current_value_fn: Callable[[Any], float | None]
    command_fn: Callable[[Any, float], str]
    min_value: float
    max_value: float
    step: float
    available_fn: Callable[[Any], bool] | None = None


NUMBERS: tuple[DatoubossNumberDescription, ...] = (
    # Bulk voltage (PCVV) - напряжение основного заряда
    DatoubossNumberDescription(
        key="battery_bulk_voltage",
        translation_key="battery_bulk_voltage",
        device_class="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        min_value=48.0,
        max_value=62.0,
        step=0.1,
        current_value_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("bulk_voltage"),
        command_fn=lambda coordinator, value: f"PCVV{value:.1f}",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Float voltage (PBFT) - напряжение поддержания
    DatoubossNumberDescription(
        key="battery_float_voltage",
        translation_key="battery_float_voltage",
        device_class="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        min_value=48.0,
        max_value=62.0,
        step=0.1,
        current_value_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("float_voltage"),
        command_fn=lambda coordinator, value: f"PBFT{value:.1f}",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Low voltage cutoff (PSDV) - порог отключения
    DatoubossNumberDescription(
        key="battery_under_voltage",
        translation_key="battery_under_voltage",
        device_class="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        min_value=42.0,
        max_value=50.0,
        step=0.1,
        current_value_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("low_voltage_cutoff"),
        command_fn=lambda coordinator, value: f"PSDV{value:.1f}",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Battery overvoltage alarm (PBVO) - порог высокого напряжения
    DatoubossNumberDescription(
        key="battery_overvoltage_alarm",
        translation_key="battery_overvoltage_alarm",
        device_class="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        min_value=50.0,
        max_value=65.0,
        step=0.1,
        current_value_fn=lambda coordinator: coordinator.data.get("heep2", {}).get("overvoltage_alarm_voltage"),
        command_fn=lambda coordinator, value: f"PBVO{value:.1f}",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Datouboss number entities."""
    runtime: DatoubossRuntimeData = entry.runtime_data
    async_add_entities(
        DatoubossNumber(runtime, entry, description) for description in NUMBERS
    )


class DatoubossNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Datouboss number entity."""

    entity_description: DatoubossNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: DatoubossRuntimeData,
        entry: ConfigEntry,
        description: DatoubossNumberDescription,
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
    def native_value(self) -> float | None:
        return self.entity_description.current_value_fn(self.runtime.coordinator)

    @property
    def native_min_value(self) -> float:
        return self.entity_description.min_value

    @property
    def native_max_value(self) -> float:
        return self.entity_description.max_value

    @property
    def native_step(self) -> float:
        return self.entity_description.step

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.available_fn is not None:
            return self.entity_description.available_fn(self.runtime.coordinator)
        return True

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        command = self.entity_description.command_fn(self.runtime.coordinator, value)
        await self.runtime.coordinator.async_send_write_command(command)