"""Coordinator for Datouboss TCP."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    DatoubossCommandError,
    DatoubossError,
    DatoubossProtocolError,
    DatoubossTcpClient,
)
from .const import (
    AC_INPUT_RANGE_MAP,
    AC_INPUT_RANGE_REVERSE,
    BATTERY_TYPE_REVERSE,
    CHARGER_SOURCE_PRIORITY_MAP,
    CHARGER_SOURCE_PRIORITY_REVERSE,
    CHARGER_SOURCE_PRIORITY_MAP_VMII,
    CHARGER_SOURCE_PRIORITY_REVERSE_VMII,
    CHARGER_SOURCE_PRIORITY_OPTIONS_CLASSIC,
    CHARGER_SOURCE_PRIORITY_OPTIONS_VMII,
    INVERTER_MODE_MAP,
    MACHINE_TYPE_REVERSE,
    OUTPUT_SOURCE_PRIORITY_MAP,
    OUTPUT_SOURCE_PRIORITY_REVERSE,
    OUTPUT_SOURCE_PRIORITY_MAP_VMII,
    OUTPUT_SOURCE_PRIORITY_REVERSE_VMII,
    OUTPUT_SOURCE_PRIORITY_OPTIONS_CLASSIC,
    OUTPUT_SOURCE_PRIORITY_OPTIONS_VMII,
    OUTPUT_MODE_REVERSE,
    PV_OK_CONDITION_REVERSE,
    PROTOCOL_CLASSIC,
    PROTOCOL_QA6248,
    PROTOCOL_VMII,
    QA6248_BATTERY_TYPES,
    QA6248_MODE_CODES,
    QA6248_OUTPUT_PRIORITY_MAP,
    QA6248_OUTPUT_PRIORITY_REVERSE,
    QA6248_CHARGER_PRIORITY_MAP,
    QA6248_CHARGER_PRIORITY_REVERSE,
    QA6248_AC_INPUT_RANGE_MAP,
    QA6248_AC_INPUT_RANGE_REVERSE,
    TOPOLOGY_REVERSE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DatoubossRuntimeData:
    """Runtime data stored on the config entry."""
    client: DatoubossTcpClient
    coordinator: "DatoubossCoordinator"


class DatoubossCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Datouboss polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: DatoubossTcpClient,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client
        self.serial: str | None = None
        self.model_name: str | None = None
        self.protocol_variant: str = client.protocol_variant
        self.supported_total_charge_currents: list[int] = []
        self.supported_ac_charge_currents: list[int] = []
        
        self._loop_counter = 0
        self._time_synced_today = False  # <-- ДОБАВЛЕНО: флаг для надежной синхронизации

    async def _async_setup(self) -> None:
        """Fetch static data quickly without blocking Home Assistant startup."""
        self.protocol_variant = PROTOCOL_QA6248
        self.model_name = "Datouboss DT4862L"
        self.serial = "qa6248_offgrid"
        
        self.supported_total_charge_currents = [10, 20, 30, 40, 50, 60, 80, 100]
        self.supported_ac_charge_currents = [2, 10, 20, 30, 40, 50, 60]
        
        _LOGGER.debug("Datouboss координатор успешно инициализирован в быстром режиме")

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the inverter."""
        if self.protocol_variant == PROTOCOL_QA6248:
            return await self._async_update_data_qa6248()
        elif self.protocol_variant == PROTOCOL_VMII:
            return await self._async_update_data_vmii()
        else:
            return await self._async_update_data_classic()

    async def _async_update_data_qa6248(self) -> dict[str, Any]:
        """Poll QA6248 inverters with smart conditional heavy polling."""
        self._loop_counter += 1
        
        # НАДЕЖНАЯ АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ: строго в 23:55 (с окном в 10 секунд)
        now = datetime.now()
        if now.hour == 23 and now.minute == 55 and now.second < 50:
            if not self._time_synced_today:
                try:
                    await self.async_set_inverter_time()
                    self._time_synced_today = True
                    _LOGGER.info("Автоматическая синхронизация времени инвертора выполнена в 23:55")
                except Exception as err:
                    _LOGGER.warning("Ошибка автоматической синхронизации времени: %s", err)
        elif now.hour == 0 and now.minute == 0:
            # Сброс флага в полночь, чтобы синхронизация сработала на следующий день
            self._time_synced_today = False
        
        try:
            hsts = await self.client.send_command("HSTS")
            await asyncio.sleep(0.5)
            
            hbat = await self.client.send_command("HBAT")
            await asyncio.sleep(0.5)
            
            hop = await self.client.send_command("HOP")
            await asyncio.sleep(0.5)
            
            hpv = await self.client.send_command("HPV")
            await asyncio.sleep(0.5)
            
            htemp = await self.client.send_command("HTEMP")
            await asyncio.sleep(0.5)
            
            hgrid = await self.client.send_command("HGRID")
            await asyncio.sleep(0.5)
            
            hpvb = await self.client.send_command("HPVB")
            await asyncio.sleep(0.5)
        except DatoubossError as err:
            raise UpdateFailed(f"Failed to read basic data: {err}") from err

        hsts_data = self._parse_hsts(hsts.raw_payload) or {}
        hbat_data = self._parse_hbat(hbat.raw_payload) or {}
        hop_data = self._parse_hop(hop.raw_payload) or {}
        hpv_data = self._parse_hpv(hpv.raw_payload) or {}
        htemp_data = self._parse_htemp(htemp.raw_payload) or {}
        hgrid_data = self._parse_hgrid(hgrid.raw_payload) or {}
        hpvb_data = self._parse_hpvb(hpvb.raw_payload) or {}

        heep1_data = self.data.get("heep1") if self.data else None
        heep2_data = self.data.get("heep2") if self.data else None
        hgen_data = self.data.get("hgen") if self.data else None

        # Тяжёлые команды опрашиваем раз в 60 циклов (~5 минут)
        if self._loop_counter == 1 or self._loop_counter >= 60:
            _LOGGER.debug("Loop %d: Запрос тяжелых команд из EEPROM инвертора...", self._loop_counter)
            self._loop_counter = 1
            
            try:
                heep1 = await self.client.send_command("HEEP1", timeout=12)
                heep1_data = self._parse_heep1(heep1.raw_payload)
                await asyncio.sleep(0.5)
            except DatoubossError:
                _LOGGER.debug("HEEP1 skipping this turn")

            try:
                heep2 = await self.client.send_command("HEEP2", timeout=12)
                heep2_data = self._parse_heep2(heep2.raw_payload)
                await asyncio.sleep(0.5)
            except DatoubossError:
                _LOGGER.debug("HEEP2 skipping this turn")

            try:
                hgen = await self.client.send_command("HGEN", timeout=10)
                hgen_data = self._parse_hgen(hgen.raw_payload)
            except DatoubossError:
                _LOGGER.debug("HGEN skipping this turn")

        result = {
            "hsts": hsts_data,
            "hbat": hbat_data,
            "hop": hop_data,
            "hpv": hpv_data,
            "htemp": htemp_data,
            "hgrid": hgrid_data,
            "hpvb": hpvb_data,
        }

        if heep1_data:
            result["heep1"] = heep1_data
        if heep2_data:
            result["heep2"] = heep2_data
        if hgen_data:
            result["hgen"] = hgen_data

        raw = {
            "HSTS": hsts.raw_payload,
            "HBAT": hbat.raw_payload,
            "HOP": hop.raw_payload,
            "HPV": hpv.raw_payload,
            "HTEMP": htemp.raw_payload,
            "HGRID": hgrid.raw_payload,
            "HPVB": hpvb.raw_payload,
        }
        if heep1_data and "raw" in heep1_data:
            raw["HEEP1"] = heep1_data["raw"]
        if heep2_data and "raw" in heep2_data:
            raw["HEEP2"] = heep2_data["raw"]
        if hgen_data and "raw" in hgen_data:
            raw["HGEN"] = hgen_data["raw"]

        result["raw"] = raw
        return result

    async def _async_update_data_vmii(self) -> dict[str, Any]:
        try:
            qmod = await self._async_vmii_query("QMOD")
            qpigs = await self._async_vmii_query("QPIGS")
            qpiri = await self._async_vmii_query("QPIRI")
            qpiws = await self._async_vmii_query("QPIWS")
        except DatoubossError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "qmod": self._parse_qmod(qmod.raw_payload),
            "qid": self.serial or "",
            "qpigs": self._parse_qpigs(qpigs.raw_payload),
            "qpiri": self._parse_qpiri(qpiri.raw_payload),
            "qpiws": self._parse_qpiws(qpiws.raw_payload),
            "raw": {
                "QMOD": qmod.raw_payload,
                "QID": self.serial or "",
                "QPIGS": qpigs.raw_payload,
                "QPIRI": qpiri.raw_payload,
                "QPIWS": qpiws.raw_payload,
            },
        }

    async def _async_update_data_classic(self) -> dict[str, Any]:
        try:
            qmod = await self.client.send_command("QMOD")
            qid = await self.client.send_command("QID")
            qpigs = await self.client.send_command("QPIGS")
            qpiri = await self.client.send_command("QPIRI")
            qpiws = await self.client.send_command("QPIWS")
        except DatoubossError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "qmod": self._parse_qmod(qmod.raw_payload),
            "qid": qid.raw_payload.lstrip("("),
            "qpigs": self._parse_qpigs(qpigs.raw_payload),
            "qpiri": self._parse_qpiri(qpiri.raw_payload),
            "qpiws": self._parse_qpiws(qpiws.raw_payload),
            "raw": {
                "QMOD": qmod.raw_payload,
                "QID": qid.raw_payload,
                "QPIGS": qpigs.raw_payload,
                "QPIRI": qpiri.raw_payload,
                "QPIWS": qpiws.raw_payload,
            },
        }

    # --- QA6248 парсеры ---
    def _parse_hsts(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 2:
            return {"error": "invalid_format", "raw": text}
        error_code = parts[0]
        mode_and_flags = parts[1]
        mode = mode_and_flags[0] if mode_and_flags else "X"
        flags_str = mode_and_flags[1:] if len(mode_and_flags) > 1 else ""
        additional_flags = parts[2] if len(parts) > 2 else ""
        all_flags = flags_str + additional_flags
        flags = {}
        flag_names = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
        for i, name in enumerate(flag_names):
            flags[name] = all_flags[i] if i < len(all_flags) else "0"
        extended_flags = {}
        extended_flag_names = ["M", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y"]
        for i, name in enumerate(extended_flag_names):
            idx = i + 12
            extended_flags[name] = all_flags[idx] if idx < len(all_flags) else "0"
        return {
            "error_code": error_code, "mode": mode, "mode_name": QA6248_MODE_CODES.get(mode, "unknown"),
            "flags": flags, "extended_flags": extended_flags, "flags_raw": all_flags,
            "output_active": flags.get("B") == "1", "battery_disconnected": flags.get("D") == "1",
            "battery_low_alarm": flags.get("C") == "1", "overload": flags.get("E") == "1",
            "overtemp": flags.get("F") == "1", "pv_power_low": flags.get("I") == "1",
            "input_voltage_high": flags.get("J") == "1", "battery_voltage_high": flags.get("K") == "1",
            "fan_fault": flags.get("L") == "1", "inverter_on": flags.get("H") == "1",
            "floating_mode": False, "scc_charging": False, "ac_charging": False, "charge_active": False, "raw": text,
        }

    def _parse_hbat(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 7:
            return {"error": "invalid_format", "raw": text}
        try:
            battery_cells = int(parts[0])
            battery_voltage = float(parts[1])
            battery_capacity = int(parts[2])
            charge_current = int(parts[3])
            discharge_current = int(parts[4])
            bus_voltage = int(parts[5])
            flags_token = parts[6]
            flags_str = flags_token[:7] if len(flags_token) >= 7 else flags_token.ljust(7, '0')
            charge_switch = int(flags_str[0]) if flags_str[0].isdigit() else 0
            solar_charge_switch = int(flags_str[1]) if flags_str[1].isdigit() else 0
            ac_charge_switch = int(flags_str[2]) if flags_str[2].isdigit() else 0
            lithium_activate_switch = int(flags_str[3]) if flags_str[3].isdigit() else 0
            lithium_activate_process = int(flags_str[4]) if flags_str[4].isdigit() else 0
            battery_status = int(flags_str[6]) if flags_str[6].isdigit() else 0
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}
        scc_charging = solar_charge_switch == 1
        ac_charging = ac_charge_switch == 1
        return {
            "battery_cells": battery_cells, "battery_voltage": battery_voltage, "battery_capacity": battery_capacity,
            "charge_current": charge_current, "discharge_current": discharge_current, "bus_voltage": bus_voltage,
            "charge_switch": charge_switch, "solar_charge_switch": solar_charge_switch, "ac_charge_switch": ac_charge_switch,
            "lithium_activate_switch": lithium_activate_switch, "lithium_activate_process": lithium_activate_process,
            "battery_status": battery_status, "battery_status_name": {0: "idle", 1: "discharging", 2: "charging"}.get(battery_status, "unknown"),
            "scc_charging": scc_charging, "ac_charging": ac_charging, "charge_active": scc_charging or ac_charging, "raw": text,
        }

    def _parse_hop(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 8:
            return {"error": "invalid_format", "raw": text}
        try:
            return {
                "output_voltage": float(parts[0]), "output_frequency": float(parts[1]),
                "apparent_power": int(parts[2]), "active_power": int(parts[3]),
                "load_percent": int(parts[4]), "dc_component": int(parts[5]),
                "internal_data": parts[6], "inductor_current": float(parts[7]), "raw": text,
            }
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_hpv(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 3:
            return {"error": "invalid_format", "raw": text}
        try:
            return {"pv_voltage": float(parts[0]), "pv_current": float(parts[1]), "pv_power": int(parts[2]), "raw": text}
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_hpvb(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 1:
            return {"error": "invalid_format", "raw": text}
        try:
            return {"scc_battery_voltage": float(parts[0]), "raw": text}
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_htemp(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 7:
            return {"error": "invalid_format", "raw": text}
        try:
            return {
                "pv_temperature": int(parts[0]), "inverter_temperature": int(parts[1]),
                "boost_temperature": int(parts[2]), "internal_data": int(parts[3]),
                "max_temperature": int(parts[4]), "fan1_speed": int(parts[5]),
                "fan2_speed": int(parts[6]), "fan1_status": int(parts[7]) if len(parts) > 7 else 0,
                "fan2_status": int(parts[8]) if len(parts) > 8 else 0, "heatsink_temperature": int(parts[1]), "raw": text,
            }
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_hgrid(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 2:
            return {"error": "invalid_format", "raw": text}
        try:
            return {"grid_voltage": float(parts[0]), "grid_frequency": float(parts[1]), "raw": text}
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_heep1(self, payload: str) -> dict[str, Any]:
        try:
            text = payload.lstrip("(").strip()
            parts = text.split()
            if len(parts) < 17:
                _LOGGER.warning("HEEP1 has only %d tokens, expected >= 17: %s", len(parts), text)
                return {"error": "invalid_format", "raw": text}
            
            work_mode = int(parts[0])
            max_total_charge_current = int(parts[1])
            max_ac_charge_current = int(parts[2])
            
            heavy_token = parts[3]
            if len(heavy_token) < 11:
                return {"error": "invalid_blob", "raw": text}
            
            ac_input_range_code = f"0{heavy_token[0]}"
            pv_grid_protocol = int(heavy_token[1]) if heavy_token[1].isdigit() else 0
            battery_type_code_raw = f"0{heavy_token[2]}"
            overload_restart = int(heavy_token[4]) if heavy_token[4].isdigit() else 0
            input_source_prompt = int(heavy_token[5]) if heavy_token[5].isdigit() else 0
            overtemp_restart = int(heavy_token[6]) if heavy_token[6].isdigit() else 0
            ac_output_rating_voltage = float(heavy_token[8:11]) if heavy_token[8:11].isdigit() else 230.0
            
            blob2 = parts[4] if len(parts) > 4 else "0"
            output_frequency = int(blob2[0]) if len(blob2) > 0 and blob2[0].isdigit() else 0
            auto_return_page1 = int(blob2[1]) if len(blob2) > 1 and blob2[1].isdigit() else 0
            charge_priority_code = f"0{blob2[2]}" if len(blob2) > 2 and blob2[2].isdigit() else "00"
            
            buzzer = int(parts[5]) if len(parts) > 5 else 0
            lcd_backlight = int(parts[6]) if len(parts) > 6 else 0
            overload_to_bypass = int(parts[7]) if len(parts) > 7 else 0
            output_mode = int(parts[8]) if len(parts) > 8 else 0
            bms_control = int(parts[9]) if len(parts) > 9 else 0
            bms_low_soc = int(parts[10]) if len(parts) > 10 else 0
            
            bulk_voltage = float(parts[14]) if len(parts) > 14 else 0.0
            float_voltage = float(parts[15]) if len(parts) > 15 else 0.0
            low_voltage_cutoff = float(parts[16]) if len(parts) > 16 else 0.0
            
        except (ValueError, IndexError) as err:
            _LOGGER.error("Failed to parse HEEP1: %s", err)
            return {"error": "parse_error", "raw": text}
        
        output_priority_code = f"0{work_mode}"
        
        return {
            "work_mode": work_mode,
            "work_mode_name": {0: "SUB", 1: "SBU", 2: "SUF", 3: "PEC"}.get(work_mode, f"unknown_{work_mode}"),
            "max_total_charge_current": max_total_charge_current,
            "max_ac_charge_current": max_ac_charge_current,
            "ac_input_range": ac_input_range_code,
            "ac_input_range_name": QA6248_AC_INPUT_RANGE_REVERSE.get(ac_input_range_code, f"unknown_{ac_input_range_code}"),
            "pv_grid_protocol": pv_grid_protocol,
            "output_source_priority": output_priority_code,
            "output_source_priority_name": QA6248_OUTPUT_PRIORITY_REVERSE.get(output_priority_code, f"unknown_{output_priority_code}"),
            "charger_source_priority": charge_priority_code,
            "charger_source_priority_name": QA6248_CHARGER_PRIORITY_REVERSE.get(charge_priority_code, f"unknown_{charge_priority_code}"),
            "battery_type": battery_type_code_raw,
            "battery_type_name": QA6248_BATTERY_TYPES.get(battery_type_code_raw, f"unknown_{battery_type_code_raw}"),
            "overload_restart": overload_restart,
            "input_source_prompt": input_source_prompt,
            "overtemp_restart": overtemp_restart,
            "ac_output_rating_voltage": ac_output_rating_voltage,
            "output_frequency": output_frequency,
            "output_frequency_name": {0: "50Hz", 1: "60Hz"}.get(output_frequency, f"unknown_{output_frequency}"),
            "auto_return_page1": auto_return_page1,
            "buzzer": buzzer,
            "lcd_backlight": lcd_backlight,
            "overload_to_bypass": overload_to_bypass,
            "output_mode": output_mode,
            "output_mode_name": {0: "SIG", 1: "PAL", 2: "3P1", 3: "3P2", 4: "3P3"}.get(output_mode, f"unknown_{output_mode}"),
            "bms_control": bms_control,
            "bms_low_soc": bms_low_soc,
            "bms_return_grid_soc": 0,
            "bms_return_battery_soc": 0,
            "bms_auto_start_soc": 0,
            "bulk_voltage": bulk_voltage,
            "float_voltage": float_voltage,
            "low_voltage_cutoff": low_voltage_cutoff,
            "raw": text,
        }

    def _parse_heep2(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 13:
            return {"error": "invalid_format", "raw": text}
        try:
            return {"overvoltage_alarm_voltage": float(parts[7]) if len(parts) > 7 else 0.0, "raw": text}
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    def _parse_hgen(self, payload: str) -> dict[str, Any]:
        text = payload.lstrip("(").strip()
        parts = text.split()
        if len(parts) < 6:
            return {"error": "invalid_format", "raw": text}
        try:
            date_str, time_str = parts[0], parts[1]
            year = 2000 + int(date_str[0:2]) if len(date_str) >= 2 else 2026
            month = int(date_str[2:4]) if len(date_str) >= 4 else 1
            day = int(date_str[4:6]) if len(date_str) >= 6 else 1
            return {
                "date": f"{year}-{month:02d}-{day:02d}", "time": time_str,
                "daily_energy": float(parts[2]), "monthly_energy": float(parts[3]),
                "yearly_energy": float(parts[4]), "total_energy": float(parts[5]), "raw": text,
            }
        except (ValueError, IndexError):
            return {"error": "parse_error", "raw": text}

    # --- Legacy парсеры ---
    def _parse_qmod(self, payload: str) -> dict[str, Any]:
        code = payload.lstrip("(")[:1]
        return {"code": code, "state": INVERTER_MODE_MAP.get(code, "unknown")}

    def _parse_qpiws(self, payload: str) -> dict[str, Any]:
        bitfield = payload.lstrip("(")
        return {"bitfield": bitfield, "active_indexes": [idx for idx, value in enumerate(bitfield) if value == "1"]}

    def _parse_qpigs(self, payload: str) -> dict[str, Any]:
        parts = payload.lstrip("(").split()
        device_status_bits = parts[16] if len(parts) > 16 else None
        device_status_bits_2 = parts[20] if len(parts) > 20 else None
        return {
            "grid_voltage": self._to_float(parts, 0), "grid_frequency": self._to_float(parts, 1),
            "output_voltage": self._to_float(parts, 2), "output_frequency": self._to_float(parts, 3),
            "output_apparent_power": self._to_int(parts, 4), "output_active_power": self._to_int(parts, 5),
            "load_percent": self._to_int(parts, 6), "bus_voltage": self._to_int(parts, 7),
            "battery_voltage": self._to_float(parts, 8), "battery_charging_current": self._to_int(parts, 9),
            "battery_capacity": self._to_int(parts, 10), "heatsink_temperature": self._to_int(parts, 11),
            "pv_battery_current": self._to_float(parts, 12), "pv_input_voltage": self._to_float(parts, 13),
            "scc_battery_voltage": self._to_float(parts, 14), "battery_discharge_current": self._to_int(parts, 15),
            "device_status_bits": device_status_bits, "device_status": self._parse_device_status_bits(device_status_bits),
            "fan_offset": parts[17] if len(parts) > 17 else None, "eeprom_version": parts[18] if len(parts) > 18 else None,
            "pv_output_power": self._to_int(parts, 19), "device_status_bits_2": device_status_bits_2,
            "device_status_2": self._parse_device_status_bits_2(device_status_bits_2),
        }

    def _parse_qpiri(self, payload: str) -> dict[str, Any]:
        parts = payload.lstrip("(").split()
        battery_type_code = self._normalize_protocol_code(parts[12] if len(parts) > 12 else None, width=1)
        ac_input_range_code = self._normalize_protocol_code(parts[15] if len(parts) > 15 else None, width=2)
        output_priority_code = self._normalize_protocol_code(parts[16] if len(parts) > 16 else None, width=2)
        charge_priority_code = self._normalize_protocol_code(parts[17] if len(parts) > 17 else None, width=2)
        machine_type_code = self._normalize_protocol_code(parts[19] if len(parts) > 19 else None, width=2)
        topology_code = self._normalize_protocol_code(parts[20] if len(parts) > 20 else None, width=1)
        output_mode_code = self._normalize_protocol_code(parts[21] if len(parts) > 21 else None, width=1)
        pv_ok_condition_code = self._normalize_protocol_code(parts[23] if len(parts) > 23 else None, width=1)
        return {
            "grid_rating_voltage": self._to_float(parts, 0), "grid_rating_current": self._to_float(parts, 1),
            "ac_output_rating_voltage": self._to_float(parts, 2), "ac_output_rating_frequency": self._to_float(parts, 3),
            "ac_output_rating_current": self._to_float(parts, 4), "ac_output_rating_apparent_power": self._to_int(parts, 5),
            "ac_output_rating_active_power": self._to_int(parts, 6), "battery_rating_voltage": self._to_float(parts, 7),
            "battery_recharge_voltage": self._to_float(parts, 8), "battery_under_voltage": self._to_float(parts, 9),
            "battery_bulk_voltage": self._to_float(parts, 10), "battery_float_voltage": self._to_float(parts, 11),
            "battery_type_code": battery_type_code, "battery_type": BATTERY_TYPE_REVERSE.get(battery_type_code, battery_type_code),
            "max_ac_charge_current": self._to_int(parts, 13), "max_total_charge_current": self._to_int(parts, 14),
            "ac_input_range_code": ac_input_range_code, "ac_input_range": AC_INPUT_RANGE_REVERSE.get(ac_input_range_code, ac_input_range_code),
            "output_source_priority_code": output_priority_code, "output_source_priority": self._resolve_output_source_priority(output_priority_code),
            "charger_source_priority_code": charge_priority_code, "charger_source_priority": self._resolve_charger_source_priority(charge_priority_code),
            "parallel_max_num": self._to_int(parts, 18), "machine_type_code": machine_type_code,
            "machine_type": MACHINE_TYPE_REVERSE.get(machine_type_code, machine_type_code),
            "topology_code": topology_code, "topology": TOPOLOGY_REVERSE.get(topology_code, topology_code),
            "output_mode_code": output_mode_code, "output_mode": OUTPUT_MODE_REVERSE.get(output_mode_code, output_mode_code),
            "battery_redischarge_voltage": self._to_float(parts, 22), "pv_ok_condition_code": pv_ok_condition_code,
            "pv_ok_condition": PV_OK_CONDITION_REVERSE.get(pv_ok_condition_code, pv_ok_condition_code),
        }

    @staticmethod
    def _to_float(parts: list[str], index: int) -> float | None:
        try: return float(parts[index])
        except (IndexError, ValueError): return None

    @staticmethod
    def _to_int(parts: list[str], index: int) -> int | None:
        try: return int(parts[index])
        except (IndexError, ValueError): return None

    @staticmethod
    def _normalize_protocol_code(code: str | None, *, width: int) -> str | None:
        if code is None: return None
        normalized = code.strip()
        if not normalized: return None
        return normalized.zfill(width) if normalized.isdigit() else normalized

    @staticmethod
    def _parse_device_status_bits(bitfield: str | None) -> dict[str, Any] | None:
        if bitfield is None or len(bitfield) < 8: return None
        bits = {7: bitfield[0], 6: bitfield[1], 5: bitfield[2], 4: bitfield[3], 3: bitfield[4], 2: bitfield[5], 1: bitfield[6], 0: bitfield[7]}
        charge_mode_bits = f"{bits[2]}{bits[1]}{bits[0]}"
        charge_mode_map = {"000": "inactive", "001": "ac_only", "010": "scc_only", "011": "scc_and_ac", "100": "charge_active_unknown_source", "101": "charge_active_ac_only", "110": "charge_active_scc_only", "111": "charge_active_scc_and_ac"}
        return {"bitfield": bitfield, "output_active": bits[4] == "1", "charge_active": bits[2] == "1", "scc_charging": bits[1] == "1", "ac_charging": bits[0] == "1", "charge_mode_bits": charge_mode_bits, "charge_mode": charge_mode_map.get(charge_mode_bits, "unknown"), "configuration_changed": bits[6] == "1", "sbu_priority_flag": bits[7] == "1", "flags": {f"b{k}": v for k, v in bits.items()}}

    @staticmethod
    def _parse_device_status_bits_2(bitfield: str | None) -> dict[str, Any] | None:
        if bitfield is None or len(bitfield) < 3: return None
        bits = {10: bitfield[0], 9: bitfield[1], 8: bitfield[2]}
        return {"bitfield": bitfield, "floating_mode": bits[10] == "1", "switch_on": bits[9] == "1", "dustproof_installed": bits[8] == "1", "flags": {f"b{k}": v for k, v in bits.items()}}

    def _resolve_output_source_priority(self, output_priority_code: str | None) -> str | None:
        if self.protocol_variant == PROTOCOL_VMII: return OUTPUT_SOURCE_PRIORITY_REVERSE_VMII.get(output_priority_code, output_priority_code)
        return OUTPUT_SOURCE_PRIORITY_REVERSE.get(output_priority_code, output_priority_code)

    def _resolve_charger_source_priority(self, charge_priority_code: str | None) -> str | None:
        if self.protocol_variant == PROTOCOL_VMII: return CHARGER_SOURCE_PRIORITY_REVERSE_VMII.get(charge_priority_code, charge_priority_code)
        return CHARGER_SOURCE_PRIORITY_REVERSE.get(charge_priority_code, charge_priority_code)

    async def async_send_write_command(self, command: str) -> str:
        """Send a write command and instantly optimize HA cache before EEPROM flushes."""
        response = await self.client.send_command(command)
        
        if self.data and "heep1" in self.data:
            heep1 = self.data["heep1"]
            
            if command.startswith("POP"):
                code = command[3:5]
                heep1["output_source_priority"] = code
                heep1["output_source_priority_name"] = QA6248_OUTPUT_PRIORITY_REVERSE.get(code, code)
                _LOGGER.debug("Optimistic cache update: output_source_priority = %s", code)
            elif command.startswith("PCP"):
                code = command[3:5]
                heep1["charger_source_priority"] = code
                heep1["charger_source_priority_name"] = QA6248_CHARGER_PRIORITY_REVERSE.get(code, code)
                _LOGGER.debug("Optimistic cache update: charger_source_priority = %s", code)
            elif command.startswith("PGR"):
                code = command[3:5]
                heep1["ac_input_range"] = code
                heep1["ac_input_range_name"] = QA6248_AC_INPUT_RANGE_REVERSE.get(code, code)
                _LOGGER.debug("Optimistic cache update: ac_input_range = %s", code)
            elif command.startswith("MUCHGC"):
                amps = int(command[6:])
                heep1["max_ac_charge_current"] = amps
                _LOGGER.debug("Optimistic cache update: max_ac_charge_current = %d", amps)
            elif command.startswith("MNCHGC"):
                amps = int(command[6:])
                heep1["max_total_charge_current"] = amps
                _LOGGER.debug("Optimistic cache update: max_total_charge_current = %d", amps)

        await asyncio.sleep(0.5)
        return response.raw_payload

    async def _async_vmii_query(self, command: str) -> Any:
        last_response = None
        for attempt in range(3):
            response = await self.client.send_command(command)
            last_response = response
            if response.crc_ok: return response
            await asyncio.sleep(0.4 * (attempt + 1))
        raise DatoubossProtocolError(f"Invalid CRC while reading {command}: {last_response.raw_payload if last_response else 'no response'}")

    def get_writable_output_source_priority_options(self) -> list[str]:
        if self.protocol_variant == PROTOCOL_QA6248: return list(QA6248_OUTPUT_PRIORITY_MAP.keys())
        if self.protocol_variant == PROTOCOL_VMII: return OUTPUT_SOURCE_PRIORITY_OPTIONS_VMII
        return OUTPUT_SOURCE_PRIORITY_OPTIONS_CLASSIC

    def get_writable_charger_source_priority_options(self) -> list[str]:
        if self.protocol_variant == PROTOCOL_QA6248: return list(QA6248_CHARGER_PRIORITY_MAP.keys())
        if self.protocol_variant == PROTOCOL_VMII: return CHARGER_SOURCE_PRIORITY_OPTIONS_VMII
        return CHARGER_SOURCE_PRIORITY_OPTIONS_CLASSIC

    def build_output_source_priority_command(self, option: str) -> str:
        if self.protocol_variant == PROTOCOL_QA6248:
            code = QA6248_OUTPUT_PRIORITY_MAP.get(option.upper())
            if code is None: raise ValueError(f"Unsupported output source priority '{option}' for this inverter")
            return f"POP{code}"
        if self.protocol_variant == PROTOCOL_VMII:
            normalized = {"sub": "SUB", "sub_priority": "SUB", "sbu": "SBU", "sbu_priority": "SBU"}.get(option.lower(), option)
            code = OUTPUT_SOURCE_PRIORITY_MAP_VMII.get(normalized)
        else:
            code = OUTPUT_SOURCE_PRIORITY_MAP.get(option)
        if code is None: raise ValueError(f"Unsupported output source priority '{option}' for this inverter")
        return f"POP{code}"

    def build_charger_source_priority_command(self, option: str) -> str:
        if self.protocol_variant == PROTOCOL_QA6248:
            code = QA6248_CHARGER_PRIORITY_MAP.get(option.upper())
            if code is None: raise ValueError(f"Unsupported charger source priority '{option}' for this inverter")
            return f"PCP{code}"
        if self.protocol_variant == PROTOCOL_VMII: code = CHARGER_SOURCE_PRIORITY_MAP_VMII.get(option)
        else: code = CHARGER_SOURCE_PRIORITY_MAP.get(option)
        if code is None: raise ValueError(f"Unsupported charger source priority '{option}' for this inverter")
        return f"PCP{code}"

    def build_ac_input_range_command(self, option: str) -> str:
        if self.protocol_variant == PROTOCOL_QA6248: code = QA6248_AC_INPUT_RANGE_MAP.get(option.upper())
        else: code = AC_INPUT_RANGE_MAP.get(option)
        if code is None: raise ValueError(f"Unsupported AC input range '{option}' for this inverter")
        return f"PGR{code}"

    def build_max_ac_charge_current_command(self, amps: int) -> str: return f"MUCHGC{amps:03d}"
    def build_max_total_charge_current_command(self, amps: int) -> str:
        if self.protocol_variant in (PROTOCOL_VMII, PROTOCOL_QA6248): return f"MNCHGC{amps:03d}"
        return f"MCHGC{amps:03d}"

    def build_set_time_command(self, dt: datetime) -> str:
        """Build command to set inverter clock.
        
        Format: ^S???DAT<YY><MM><DD><HH><MM><SS><crc16>
        Example: ^S???DAT261019211100 = 2026-10-19 21:11:00
        """
        yy = dt.strftime("%y")
        mm = dt.strftime("%m")
        dd = dt.strftime("%d")
        hh = dt.strftime("%H")
        mi = dt.strftime("%M")
        ss = dt.strftime("%S")
        return f"^S???DAT{yy}{mm}{dd}{hh}{mi}{ss}"

    async def async_set_inverter_time(self) -> str:
        """Sync inverter clock with Home Assistant time automatically."""
        now = datetime.now()
        command = self.build_set_time_command(now)
        response = await self.client.send_command(command)
        _LOGGER.info("Inverter time auto-synced to: %s (command: %s)", now.strftime("%Y-%m-%d %H:%M:%S"), command)
        await asyncio.sleep(0.5)
        return response.raw_payload

    async def async_send_raw_command(self, command: str, *, expect_response: bool = True, refresh: bool = False) -> dict[str, Any]:
        response = await self.client.send_command(command, expect_response=expect_response)
        if refresh: await self.async_refresh()
        return {"command": command, "payload": response.raw_payload, "crc_ok": response.crc_ok, "raw_frame_hex": response.raw_frame_hex}