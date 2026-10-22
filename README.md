# Datouboss QA6248 Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A local Home Assistant integration for Datouboss hybrid inverters using the **QA6248 protocol** via RS232 serial connection. No cloud dependencies, no Wi-Fi loggers, no delays — just direct, real-time communication with your inverter.

> **Based on the excellent work of [@Rkn21](https://github.com/Rkn21/datouboss_tcp_hacs)** — this integration extends the original `datouboss_tcp` project with dedicated support for the QA6248 protocol and serial (RS232) transport.

---

##  Supported Devices

| Model | Power | Battery | Protocol |
|-------|-------|---------|----------|
| **Datouboss DT4862L** | 6.2 kW | 48V | QA6248 |

> **Note:** May also work with other inverters using the QA6248 protocol (some Easun, Techfine, and other Deye/Sunsynk OEM clones). Tested and verified specifically for the DT4862L.

---

## ⚡ Features

### Real-Time Monitoring
- ☀️ **PV (Solar)**: Voltage, current, power, temperature
- 🔋 **Battery**: Voltage, charge/discharge current, SOC (%), temperature
- ⚡ **Grid**: Voltage, frequency, power flow direction
-  **Load**: Output voltage, frequency, active/apparent power, load percentage
- 📊 **Energy Statistics**: Daily, monthly, yearly, and total generation (kWh)
- 🌡️ **Temperatures**: PV, inverter, boost, max temperature
- 🔄 **Status Flags**: Output active, charging status, fault codes, warnings

### Device Control
- 🎛️ **Output Source Priority**: SUB (Grid First), SBU (Solar-Battery-Grid), SUF, PEC
- 🔋 **Charger Source Priority**: CSO (Solar First), SNU (Solar+Grid), OSO (Solar Only), SOR
- ⚡ **AC Input Range**: APL (Wide 90-280V) / UPS (Narrow 170-280V)
- 🔋 **Battery Settings**: Bulk voltage, float voltage, under-voltage cutoff, overvoltage alarm
- ⚙️ **Charge Current Limits**: Max AC charge current, max total charge current
- 🔊 **Device Settings**: Buzzer, LCD backlight, auto-return, overload/overtemp restart, BMS control

### Advanced Features
- ⏱️ **Automatic Time Sync**: Inverter clock syncs with Home Assistant daily at 23:55
- 📡 **Optimistic Cache Updates**: Instant UI feedback when changing settings (no waiting for next poll cycle)
- 🔧 **Raw Command Service**: Send any QA6248 command directly from Home Assistant
-  **Smart Polling**: Heavy EEPROM commands (HEEP1, HEEP2, HGEN) queried only once per 5 minutes to ensure RS232 stability

---

## 🔌 Physical Connection (RS232)

This integration uses a **direct serial connection** via USB-to-RS232 adapter — no Wi-Fi, no cloud, no TCP bridges required.

### Wiring Diagram

**RS232 9-Pin Connector (Female on Inverter):**

| Inverter Pin | Signal | USB-RS232 Adapter |
|:---:|:---:|:---:|
| **Pin 2** | TX (Transmit) | → **RX** |
| **Pin 3** | RX (Receive) | → **TX** |
| **Pin 5** | GND (Ground) | → **GND** |

### Hardware Requirements

- **USB-to-RS232 Adapter** with FT232RL or CP2102 chip (recommended)
  - ⚠️ Avoid cheap CH340 adapters — they may be unstable at 2400 baud
- **USB extension cable** (if needed to reach your Home Assistant server)
- **9-pin female RS232 connector** (if not included with adapter)

### Serial Port Settings

| Parameter | Value |
|-----------|-------|
| Baud Rate | **2400** |
| Data Bits | 8 |
| Stop Bits | 1 |
| Parity | None |
| Flow Control | None |

> **Linux/Armbian:** Port usually appears as `/dev/ttyUSB0`  
> **Windows:** Port usually appears as `COM3` (check Device Manager)

---

## 📥 Installation

### Option 1: Via HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant.
2. Go to **HACS** → **Integrations** → **⋮** (top-right menu) → **Custom repositories**.
3. Add repository URL: `https://github.com/SitifDm/datouboss_qa6248`
4. Select category: **Integration**.
5. Click **Add**, then **Install**.
6. **Restart Home Assistant**.

### Option 2: Manual Installation

1. Download the latest release from this repository (Code → Download ZIP).
2. Extract the `datouboss_qa6248` folder.
3. Copy it to your Home Assistant `config/custom_components/` directory.
4. **Restart Home Assistant**.

---

## ⚙️ Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Datouboss QA6248 (RS232)**.
3. Fill in the configuration form:

| Field | Value | Description |
|-------|-------|-------------|
| **Transport** | `Serial (USB console cable)` | Connection type |
| **Serial device** | `/dev/ttyUSB0` | Path to your USB serial port |
| **Baud rate** | `2400` | Serial speed (QA6248 standard) |
| **Protocol / model** | `QA6248 (Datouboss DT4862L)` | Protocol variant |
| **Name** | `Datouboss Inverter` | Friendly name |
| **Scan interval** | `5` seconds | Polling frequency |
| **Timeout** | `5` seconds | Command timeout |

4. Click **Submit**. The integration will probe the inverter and create all entities automatically.

---

## 📊 Available Entities

### Sensors (Read-Only)
- `sensor.datouboss_mode` (Current operating mode)
- `sensor.datouboss_grid_voltage` / `sensor.datouboss_grid_frequency`
- `sensor.datouboss_output_voltage` / `sensor.datouboss_output_frequency`
- `sensor.datouboss_output_active_power` / `sensor.datouboss_output_apparent_power`
- `sensor.datouboss_load_percent`
- `sensor.datouboss_bus_voltage`
- `sensor.datouboss_battery_voltage` / `sensor.datouboss_battery_capacity` (%)
- `sensor.datouboss_battery_charging_current` / `sensor.datouboss_battery_discharge_current`
- `sensor.datouboss_pv_input_voltage` / `sensor.datouboss_pv_output_power` / `sensor.datouboss_pv_current`
- `sensor.datouboss_scc_battery_voltage`
- `sensor.datouboss_heatsink_temperature` / `sensor.datouboss_pv_temperature` / `sensor.datouboss_boost_temperature`
- `sensor.datouboss_daily_energy` / `sensor.datouboss_monthly_energy` / `sensor.datouboss_yearly_energy` / `sensor.datouboss_total_energy` (kWh)

### Binary Sensors (On/Off Status)
- `binary_sensor.datouboss_output_active` / `binary_sensor.datouboss_charge_active`
- `binary_sensor.datouboss_scc_charging` / `binary_sensor.datouboss_ac_charging`
- `binary_sensor.datouboss_battery_disconnected` / `binary_sensor.datouboss_battery_low_alarm`
- `binary_sensor.datouboss_overload` / `binary_sensor.datouboss_overtemp`
- `binary_sensor.datouboss_pv_power_low` / `binary_sensor.datouboss_input_voltage_high`
- `binary_sensor.datouboss_battery_voltage_high` / `binary_sensor.datouboss_fan_fault`

### Numbers (Configurable Values)
- `number.datouboss_battery_bulk_voltage` (48.0 – 62.0 V)
- `number.datouboss_battery_float_voltage` (48.0 – 62.0 V)
- `number.datouboss_battery_under_voltage` (42.0 – 50.0 V)
- `number.datouboss_battery_overvoltage_alarm` (50.0 – 65.0 V)

### Selects (Dropdown Options)
- `select.datouboss_output_source_priority` (SUB, SBU, SUF, PEC)
- `select.datouboss_charger_source_priority` (CSO, SNU, OSO, SOR)
- `select.datouboss_ac_input_range` (APL, UPS)
- `select.datouboss_max_ac_charge_current` (2A – 60A)
- `select.datouboss_max_total_charge_current` (10A – 100A)

### Switches (On/Off Toggles)
- `switch.datouboss_buzzer`
- `switch.datouboss_overload_restart`
- `switch.datouboss_overtemp_restart`
- `switch.datouboss_lcd_backlight`
- `switch.datouboss_auto_return_page1`
- `switch.datouboss_input_source_prompt`
- `switch.datouboss_bms_control`

---

## 🛠️ Services

- **`datouboss_qa6248.send_command`**: Send a raw QA6248 command (CRC and `\r` appended automatically).
- **`datouboss_qa6248.refresh`**: Force an immediate refresh of all sensors.
- **`datouboss_qa6248.set_output_source_priority`**: Change output source priority.
- **`datouboss_qa6248.set_charger_source_priority`**: Change charger source priority.
- **`datouboss_qa6248.set_ac_input_range`**: Change AC input voltage range.
- **`datouboss_qa6248.set_max_ac_charge_current`**: Set maximum grid charging current (amps).
- **`datouboss_qa6248.set_max_total_charge_current`**: Set maximum total charging current (amps).

---

## 🔧 Troubleshooting

- **No response from inverter**: Verify RS232 wiring (Pin 2→RX, Pin 3→TX, Pin 5→GND), check baud rate is **2400**, and ensure you are using an FT232RL or CP2102 adapter.
- **Integration fails to connect**: Ensure no other application is using the serial port. On Linux, check permissions: `sudo usermod -a -G dialout homeassistant`.
- **Incorrect sensor values**: Verify protocol variant is set to **QA6248** in the config flow.

---

## 🙏 Acknowledgments

This integration is based on the outstanding work of **[@Rkn21](https://github.com/Rkn21/datouboss_tcp_hacs)**, who created the original `datouboss_tcp` integration. This project extends that foundation with dedicated QA6248 protocol support and optimized serial communication.

---

## 📄 License

This project is licensed under the MIT License.

---

**Enjoy your local, cloud-free inverter monitoring!** ⚡
