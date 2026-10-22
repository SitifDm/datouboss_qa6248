"""Switch platform for Datouboss TCP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN, PROTOCOL_QA6248
from .coordinator import DatoubossRuntimeData


@dataclass(frozen=True, kw_only=True)
class DatoubossSwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[Any], bool | None]
    turn_on_command: str
    turn_off_command: str
    available_fn: Callable[[Any], bool] | None = None


SWITCHES: tuple[DatoubossSwitchDescription, ...] = (
    # Buzzer (蜂鸣器)
    DatoubossSwitchDescription(
        key="buzzer",
        translation_key="buzzer",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("buzzer") == 1,
        turn_on_command="PEa",
        turn_off_command="PDa",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Overload restart (过载重启)
    DatoubossSwitchDescription(
        key="overload_restart",
        translation_key="overload_restart",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("overload_restart") == 1,
        turn_on_command="PEu",
        turn_off_command="PDu",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Overtemp restart (过温重启)
    DatoubossSwitchDescription(
        key="overtemp_restart",
        translation_key="overtemp_restart",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("overtemp_restart") == 1,
        turn_on_command="PEv",
        turn_off_command="PDv",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Backlight (背光)
    DatoubossSwitchDescription(
        key="lcd_backlight",
        translation_key="lcd_backlight",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("lcd_backlight") == 1,
        turn_on_command="PEx",
        turn_off_command="PDx",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Auto return to page 1 (自动返回第一页)
    DatoubossSwitchDescription(
        key="auto_return_page1",
        translation_key="auto_return_page1",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("auto_return_page1") == 1,
        turn_on_command="PEk",
        turn_off_command="PDk",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # Input source prompt (输入源提示功能)
    DatoubossSwitchDescription(
        key="input_source_prompt",
        translation_key="input_source_prompt",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("input_source_prompt") == 1,
        turn_on_command="PEy",
        turn_off_command="PDy",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
    # BMS communication control (BMS通信控制功能)
    DatoubossSwitchDescription(
        key="bms_control",
        translation_key="bms_control",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda coordinator: coordinator.data.get("heep1", {}).get("bms_control") == 1,
        turn_on_command="BMSC01",
        turn_off_command="BMSC00",
        available_fn=lambda coordinator: coordinator.protocol_variant == PROTOCOL_QA6248,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Datouboss switch entities."""
    runtime: DatoubossRuntimeData = entry.runtime_data
    async_add_entities(
        DatoubossSwitch(runtime, entry, description) for description in SWITCHES
    )


class DatoubossSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Datouboss switch entity."""

    entity_description: DatoubossSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: DatoubossRuntimeData,
        entry: ConfigEntry,
        description: DatoubossSwitchDescription,
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
        return self.entity_description.is_on_fn(self.runtime.coordinator)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.available_fn is not None:
            return self.entity_description.available_fn(self.runtime.coordinator)
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.runtime.coordinator.async_send_write_command(
            self.entity_description.turn_on_command
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.runtime.coordinator.async_send_write_command(
            self.entity_description.turn_off_command
        )