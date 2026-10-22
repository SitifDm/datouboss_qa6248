"""Base client for Datouboss / Voltronic inverters.
Handles protocol detection, frame building, CRC calculation, and response decoding.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from .const import (
    PROTOCOL_CLASSIC,
    PROTOCOL_QA6248,
    PROTOCOL_VMII,
    QA6248_READ_COMMANDS,
    QA6248_WRITE_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)


# ------------------------------ exceptions ------------------------------

class DatoubossError(Exception):
    """Base exception for Datouboss errors."""


class DatoubossConnectionError(DatoubossError):
    """Connection-level error (port open, write, etc.)."""


class DatoubossProtocolError(DatoubossError):
    """Protocol-level error (no response, CRC mismatch, etc.)."""


class DatoubossCommandError(DatoubossProtocolError):
    """Inverter rejected the command (NAK response)."""


# ------------------------------ response ------------------------------

@dataclass(frozen=True)
class CommandResponse:
    """Decoded response from the inverter."""
    command: str
    raw_frame_hex: str
    raw_payload: str
    crc_ok: bool


# ------------------------------ CRC ------------------------------

def _crc16_xmodem(data: bytes) -> int:
    """Calculate CRC16/XMODEM checksum."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _escape_crc_bytes(crc_bytes: bytes) -> bytes:
    """Escape 0x28, 0x0D, 0x0A in CRC bytes per Voltronic protocol."""
    result = bytearray()
    for b in crc_bytes:
        if b in (0x28, 0x0D, 0x0A):
            result.append(b + 1)
        else:
            result.append(b)
    return bytes(result)


def _protocol_crc_bytes(payload: bytes) -> bytes:
    """Return 2-byte CRC for the given payload (without escaping)."""
    crc = _crc16_xmodem(payload)
    return crc.to_bytes(2, "big")


# ------------------------------ frame building ------------------------------

class DatoubossTcpClient:
    """Protocol brain shared by TCP and serial clients."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: int = 5,
        *,
        protocol_variant: str = PROTOCOL_CLASSIC,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._configured_protocol = protocol_variant
        self._detected_protocol: str | None = None
        self._model_name: str | None = None

    @property
    def protocol_variant(self) -> str:
        if self._configured_protocol != "auto":
            return self._configured_protocol
        return self._detected_protocol or PROTOCOL_CLASSIC

    @property
    def model_name(self) -> str | None:
        return self._model_name

    @staticmethod
    def _get_base_command(command: str) -> str:
        """Extract base command name (strip trailing parameters).
        
        Handles:
        - Standard commands: HEEP1 -> HEEP1, POP01 -> POP
        - Special commands: ^S???DAT261019220910 -> ^S???DAT
        """
        # Special commands starting with ^S???
        if command.startswith("^S???"):
            return command[:7]  # e.g., "^S???DAT", "^S???CLE"
        
        # Standard commands: letters + optional digits
        match = re.match(r"^[A-Z]+\d*", command)
        return match.group(0) if match else command

    @staticmethod
    def build_frame(command: str) -> bytes:
        """Build a complete frame for the given command.
        
        QA6248 read commands (HSTS, HBAT, HOP, HPV, HTEMP, HGRID, HGEN, HEEP1, etc.):
            No CRC, just command + \r
        QA6248 write commands (POP01, PCP02, PGR00, MUCHGC030, ^S???DAT, etc.):
            Command + CRC16 + \r
        """
        base_cmd = DatoubossTcpClient._get_base_command(command)
        
        # QA6248 read commands — NO CRC
        if base_cmd in QA6248_READ_COMMANDS:
            return f"{command}\r".encode("ascii")
        
        # Write commands or legacy — WITH CRC
        payload = command.encode("ascii")
        crc_bytes = _escape_crc_bytes(_protocol_crc_bytes(payload))
        return payload + crc_bytes + b"\r"

    @staticmethod
    def _split_frames(raw: bytes) -> list[bytes]:
        """Split raw bytes into individual frames (separated by \r)."""
        if not raw:
            return []
        parts = raw.split(b"\r")
        return [p + b"\r" for p in parts if p]

    @staticmethod
    def _decode_frame(command: str, raw: bytes) -> CommandResponse | None:
        """Decode a raw frame into a CommandResponse."""
        if len(raw) < 2:
            return None
        
        base_cmd = DatoubossTcpClient._get_base_command(command)
        
        # QA6248 read commands: NO CRC in response
        if base_cmd in QA6248_READ_COMMANDS:
            payload = raw[:-1] if raw.endswith(b"\r") else raw
            return CommandResponse(
                command=command,
                raw_frame_hex=raw.hex(" "),
                raw_payload=payload.decode("ascii", errors="replace"),
                crc_ok=True,
            )
        
        # Special commands (^S???DAT, ^S???CLE, etc.): response is "^1 ^A\r" without CRC
        if base_cmd.startswith("^S???"):
            payload = raw[:-1] if raw.endswith(b"\r") else raw
            payload_str = payload.decode("ascii", errors="replace")
            # Accept "^1 ^A" or "(ACK" as success
            success = payload_str.startswith("^1") or payload_str == "(ACK"
            return CommandResponse(
                command=command,
                raw_frame_hex=raw.hex(" "),
                raw_payload=payload_str,
                crc_ok=success,
            )
        
        # Write commands or legacy: expect CRC
        if len(raw) >= 5 and raw.endswith(b"\r"):
            payload = raw[:-3]
            rx_crc = int.from_bytes(raw[-3:-1], "big")
            calc_crc = int.from_bytes(_protocol_crc_bytes(payload), "big")
            return CommandResponse(
                command=command,
                raw_frame_hex=raw.hex(" "),
                raw_payload=payload.decode("ascii", errors="replace"),
                crc_ok=rx_crc == calc_crc,
            )
        
        return None

    @staticmethod
    def find_matching_response(
        command: str, responses: list[CommandResponse]
    ) -> CommandResponse | None:
        """Find the response that matches the sent command."""
        base_cmd = DatoubossTcpClient._get_base_command(command)
        for resp in responses:
            if base_cmd in QA6248_READ_COMMANDS:
                # For read commands, any response with valid payload matches
                if resp.raw_payload and not resp.raw_payload.startswith("(NAK"):
                    return resp
            elif base_cmd.startswith("^S???"):
                # Special commands return "^1 ^A" or "(ACK"
                if resp.raw_payload and (resp.raw_payload.startswith("^1") or resp.raw_payload == "(ACK"):
                    return resp
            else:
                # For write commands, look for ACK/NAK
                if resp.raw_payload in ("(ACK", "(NAK"):
                    return resp
        return None

    # ------------------------------ public API (TCP) ------------------------------

    async def send_command(
        self,
        command: str,
        *,
        expect_response: bool = True,
        timeout: int | None = None,
    ) -> CommandResponse:
        """Send a command and return the response. Override in TCP client."""
        raise NotImplementedError("Use DatoubossSerialClient or TCP client subclass")

    async def ensure_protocol(self) -> str:
        """Resolve the protocol variant. Override in serial client."""
        raise NotImplementedError("Use DatoubossSerialClient or TCP client subclass")

    async def fetch_supported_currents(self, command: str) -> list[int]:
        """Fetch supported charge currents. Override in serial client."""
        raise NotImplementedError("Use DatoubossSerialClient or TCP client subclass")

    async def probe(self) -> dict[str, Any]:
        """Probe the inverter. Override in serial client."""
        raise NotImplementedError("Use DatoubossSerialClient or TCP client subclass")