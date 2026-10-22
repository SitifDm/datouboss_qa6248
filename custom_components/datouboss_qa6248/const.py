"""Constants for the Datouboss TCP integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "datouboss_tcp"
PLATFORMS = ["sensor", "select", "binary_sensor", "number", "switch"]
DEFAULT_NAME = "Datouboss Inverter"
DEFAULT_PORT = 8886
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_TIMEOUT = 5
DEFAULT_PROTOCOL = "auto"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_SERIAL = "serial"
CONF_PROTOCOL = "protocol_variant"

PROTOCOL_AUTO = "auto"
PROTOCOL_CLASSIC = "classic"
PROTOCOL_VMII = "vmii_max"
PROTOCOL_QA6248 = "qa6248"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_COMMAND = "command"
ATTR_MODE = "mode"
ATTR_AMPS = "amps"
ATTR_REFRESH = "refresh"
ATTR_EXPECT_RESPONSE = "expect_response"

SERVICE_SEND_COMMAND = "send_command"
SERVICE_REFRESH = "refresh"
SERVICE_SET_OUTPUT_SOURCE_PRIORITY = "set_output_source_priority"
SERVICE_SET_CHARGER_SOURCE_PRIORITY = "set_charger_source_priority"
SERVICE_SET_AC_INPUT_RANGE = "set_ac_input_range"
SERVICE_SET_MAX_AC_CHARGE_CURRENT = "set_max_ac_charge_current"
SERVICE_SET_MAX_TOTAL_CHARGE_CURRENT = "set_max_total_charge_current"

# --- QA6248 Protocol ---
QA6248_READ_COMMANDS = {
    "QPRTL", "HSTS", "HSTS2", "HIMSG1", "HGRID", "HOP", "HBAT",
    "HPV", "HTEMP", "HEEP1", "HBMS1", "HBMS2", "HBMS3", "HGEN",
    "HPVB", "HEEP2", "HEEP3", "HCTMSG1", "F",
}

QA6248_WRITE_COMMANDS = {
    "PE", "PD", "V", "PBT", "PSDV", "PCVV", "PBFT",
    "MNCHGC", "MUCHGC", "PGR", "POP", "BMSC", "PF", "PBVO",
    "BMSSDC", "BMSB2UC", "BMSU2BC", "BMSSRC", "PBCV", "PBDV",
    "PGFC", "GFP", "DISCC", "PDAULC", "PDSDV", "PDSDS",
    "PBEQE", "PBEQV", "PBEQT", "PBEQOT", "PBEQP", "PCP",
    "POPM", "PDDCGT", "PDDLYT", "PDSRV", "PDSRS",
    "HOSTCRCEN", "HOSTCRCDN",
}

QA6248_MODE_CODES = {
    "P": "power_on", "S": "standby", "L": "line", "B": "battery",
    "F": "fault", "D": "shutdown", "X": "test_mode",
}

# Типы батарей (согласно протоколу HEEP1, пункт 7)
QA6248_BATTERY_TYPES = {
    "00": "agm", "01": "flooded", "02": "user", "03": "lithium_ion",
    "04": "pylontech", "05": "tqf", "06": "growatt", "07": "lib",
    "08": "lic", "09": "fel",
}
QA6248_BATTERY_TYPES_REVERSE = {v: k for k, v in QA6248_BATTERY_TYPES.items()}

# Приоритеты выхода (POP)
QA6248_OUTPUT_PRIORITY_MAP = {"SUB": "00", "SBU": "01"}
QA6248_OUTPUT_PRIORITY_REVERSE = {v: k for k, v in QA6248_OUTPUT_PRIORITY_MAP.items()}
QA6248_OUTPUT_PRIORITY_OPTIONS = list(QA6248_OUTPUT_PRIORITY_MAP.keys())

# Приоритеты заряда (PCP)
QA6248_CHARGER_PRIORITY_MAP = {"CSO": "00", "SNU": "01", "OSO": "02"}
QA6248_CHARGER_PRIORITY_REVERSE = {v: k for k, v in QA6248_CHARGER_PRIORITY_MAP.items()}
QA6248_CHARGER_PRIORITY_OPTIONS = list(QA6248_CHARGER_PRIORITY_MAP.keys())

# Диапазон входа AC (PGR) - СТРОГО по протоколу: 0=APL, 1=UPS
QA6248_AC_INPUT_RANGE_MAP = {
    "APL": "00",  # 0: APL (Широкий диапазон, Бытовая техника)
    "UPS": "01",  # 1: UPS (Узкий диапазон, ИБП)
}
QA6248_AC_INPUT_RANGE_REVERSE = {v: k for k, v in QA6248_AC_INPUT_RANGE_MAP.items()}
QA6248_AC_INPUT_RANGE_OPTIONS = list(QA6248_AC_INPUT_RANGE_MAP.keys())

# --- Legacy / VMII маппинги ---
OUTPUT_SOURCE_PRIORITY_MAP = {"utility_first": "00", "solar_first": "01", "sbu_priority": "02"}
OUTPUT_SOURCE_PRIORITY_REVERSE = {value: key for key, value in OUTPUT_SOURCE_PRIORITY_MAP.items()}
OUTPUT_SOURCE_PRIORITY_OPTIONS_CLASSIC = list(OUTPUT_SOURCE_PRIORITY_MAP.keys())

OUTPUT_SOURCE_PRIORITY_MAP_VMII = {"SUB": "00", "SBU": "01"}
OUTPUT_SOURCE_PRIORITY_REVERSE_VMII = {value: key for key, value in OUTPUT_SOURCE_PRIORITY_MAP_VMII.items()}
OUTPUT_SOURCE_PRIORITY_OPTIONS_VMII = ["SUB", "SBU"]

CHARGER_SOURCE_PRIORITY_MAP = {"utility_first": "00", "solar_first": "01", "solar_and_utility": "02", "solar_only": "03"}
CHARGER_SOURCE_PRIORITY_REVERSE = {value: key for key, value in CHARGER_SOURCE_PRIORITY_MAP.items()}
CHARGER_SOURCE_PRIORITY_OPTIONS_CLASSIC = list(CHARGER_SOURCE_PRIORITY_MAP.keys())

CHARGER_SOURCE_PRIORITY_MAP_VMII = {"solar_first": "00", "solar_and_utility": "01", "solar_only": "02"}
CHARGER_SOURCE_PRIORITY_REVERSE_VMII = {value: key for key, value in CHARGER_SOURCE_PRIORITY_MAP_VMII.items()}
CHARGER_SOURCE_PRIORITY_OPTIONS_VMII = ["solar_first", "solar_and_utility", "solar_only"]

AC_INPUT_RANGE_MAP = {"APL (20ms/90-280 Vac)": "00", "UPS (10ms/170-280 Vac)": "01"}
AC_INPUT_RANGE_REVERSE = {value: key for key, value in AC_INPUT_RANGE_MAP.items()}

BATTERY_TYPE_REVERSE = {"0": "agm", "1": "flooded", "2": "custom", "3": "lithium"}
MACHINE_TYPE_REVERSE = {"00": "grid_tie", "01": "off_grid", "10": "hybrid"}
TOPOLOGY_REVERSE = {"0": "transformerless", "1": "transformer"}
OUTPUT_MODE_REVERSE = {"0": "single_machine", "1": "parallel_output", "2": "phase_1_of_3_phase", "3": "phase_2_of_3_phase", "4": "phase_3_of_3_phase"}
PV_OK_CONDITION_REVERSE = {"0": "pv_ok_if_one_inverter_has_pv", "1": "pv_ok_if_all_inverters_have_pv"}
INVERTER_MODE_MAP = {"P": "power_on", "S": "standby", "L": "line", "B": "battery", "F": "fault", "H": "power_saving", "D": "shutdown"}

UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

CONF_TRANSPORT = "transport"
TRANSPORT_TCP = "tcp"
TRANSPORT_SERIAL = "serial"
DEFAULT_TRANSPORT = TRANSPORT_TCP

CONF_SERIAL_DEVICE = "serial_device"
CONF_BAUDRATE = "baudrate"
DEFAULT_SERIAL_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 2400
BAUDRATE_OPTIONS = [2400, 9600, 19200, 115200]

CRC_RESERVED_BYTES = {0x28, 0x0D, 0x0A}