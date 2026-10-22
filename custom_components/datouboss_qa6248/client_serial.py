"""Serial client for Datouboss / Voltronic inverters over a USB console cable.
Uses plain pyserial (a Home Assistant core dependency) with executor-thread
reads, so no extra runtime requirements are needed.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import serial

from .client import (
    CommandResponse,
    DatoubossCommandError,
    DatoubossConnectionError,
    DatoubossError,
    DatoubossProtocolError,
    DatoubossTcpClient,
)
from .const import (
    DEFAULT_PROTOCOL,
    PROTOCOL_AUTO,
    PROTOCOL_CLASSIC,
    PROTOCOL_QA6248,
    PROTOCOL_VMII,
)

_LOGGER = logging.getLogger(__name__)


class DatoubossSerialClient:
    """Persistent-port serial client reusing the TCP client's protocol brain."""

    def __init__(
        self,
        device: str,
        baudrate: int,
        timeout: int,
        *,
        protocol_variant: str = DEFAULT_PROTOCOL,
    ) -> None:
        self._device = device
        self._baudrate = baudrate
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._port: serial.Serial | None = None
        self._configured_protocol = protocol_variant
        self._detected_protocol: str | None = None
        self._model_name: str | None = None

    @property
    def protocol_variant(self) -> str:
        if self._configured_protocol != PROTOCOL_AUTO:
            return self._configured_protocol
        return self._detected_protocol or PROTOCOL_CLASSIC

    @property
    def model_name(self) -> str | None:
        return self._model_name

    # ------------------------------ transport ------------------------------

    def _ensure_open(self) -> None:
        if self._port is not None and self._port.is_open:
            return
        try:
            self._port = serial.Serial(
                port=self._device,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
                write_timeout=2.0,
                rtscts=False,
                dsrdtr=False,
            )
        except (OSError, serial.SerialException) as err:
            self._port = None
            raise DatoubossConnectionError(
                f"Unable to open serial port {self._device}"
            ) from err

    def _write_frame(self, frame: bytes) -> None:
        """Write frame to serial port. CRC is already handled by build_frame."""
        assert self._port is not None
        self._port.write(frame)
        self._port.flush()

    def _drop(self) -> None:
        """Close the serial port immediately and safely."""
        port, self._port = self._port, None
        if port is not None and port.is_open:
            try:
                port.close()
            except Exception:  # noqa: BLE001
                pass

    async def close(self) -> None:
        """Close the serial port."""
        async with self._lock:
            if self._port is not None:
                await asyncio.get_running_loop().run_in_executor(None, self._drop)

    def _read_until_idle_sync(self, total_timeout: float, quiet_timeout: float) -> bytes:
        """Синхронное чтение из порта до наступления тишины."""
        assert self._port is not None
        if self._port.timeout is None:
            self._port.timeout = 1.0

        chunks = bytearray()
        start_time = time.time()
        deadline = start_time + total_timeout
        
        while True:
            if self._port is None or not self._port.is_open:
                break
                
            if time.time() > deadline:
                break
                
            remaining = deadline - time.time()
            self._port.timeout = min(quiet_timeout, remaining, 1.0)
            
            try:
                data = self._port.read(128)
            except serial.SerialException:
                break
                
            if data:
                chunks.extend(data)
                start_time = time.time()
                
                if b'\r' in data:
                    break
            else:
                if time.time() - start_time >= quiet_timeout:
                    break
                    
        return bytes(chunks)

    async def _read_until_idle(
        self, total_timeout: float, quiet_timeout: float
    ) -> bytes:
        return await asyncio.get_running_loop().run_in_executor(
            None, self._read_until_idle_sync, total_timeout, quiet_timeout
        )

    async def _send_and_collect(
        self, command: str, *, timeout: int | None = None
    ) -> list[CommandResponse]:
        # build_frame УЖЕ добавляет CRC для команд записи и убирает для чтения!
        frame = DatoubossTcpClient.build_frame(command)
        effective_timeout = timeout or self._timeout
        
        is_heavy_cmd = command in ("HEEP1", "HEEP2", "HEEP3", "HIMSG1", "HGEN")
        
        if command in ("HEEP1", "HEEP2", "HEEP3", "HIMSG1"):
            quiet_timeout = 2.0
            effective_timeout = max(effective_timeout, 10)
        elif command == "HGEN":
            quiet_timeout = 1.5
            effective_timeout = max(effective_timeout, 8)
        else:
            quiet_timeout = 0.5
            effective_timeout = max(effective_timeout, 5)
        
        preflush_timeout = min(0.3, max(0.1, effective_timeout / 8))
        loop = asyncio.get_running_loop()

        async with self._lock:
            try:
                if command == "HEEP1" and self._port is not None:
                    _LOGGER.debug("Принудительное переоткрытие порта перед первой тяжелой командой HEEP1")
                    await loop.run_in_executor(None, self._drop)
                    await asyncio.sleep(0.2)

                await loop.run_in_executor(None, self._ensure_open)
                
                stale = await self._read_until_idle(preflush_timeout, quiet_timeout)
                if stale:
                    _LOGGER.debug(
                        "Discarded stale Datouboss data before %s: %s",
                        command,
                        stale.hex(" "),
                    )
                await loop.run_in_executor(None, self._write_frame, frame)
                raw = await self._read_until_idle(effective_timeout, quiet_timeout)
            except (OSError, serial.SerialException) as err:
                await loop.run_in_executor(None, self._drop)
                raise DatoubossConnectionError(
                    f"Serial failure while waiting for inverter response to {command}"
                ) from err

        responses = [
            decoded
            for raw_frame in DatoubossTcpClient._split_frames(raw)
            if (decoded := DatoubossTcpClient._decode_frame(command, raw_frame)) is not None
        ]

        if responses:
            _LOGGER.debug(
                "Datouboss serial command=%s tx=%s rx_frames=%s",
                command,
                frame.hex(" "),
                [
                    {
                        "payload": response.raw_payload,
                        "crc_ok": response.crc_ok,
                        "raw": response.raw_frame_hex,
                    }
                    for response in responses
                ],
            )

        return responses

    # ------------------------------ public API ------------------------------

    async def send_command_bundle(
        self, command: str, *, timeout: int | None = None
    ) -> list[CommandResponse]:
        responses = await self._send_and_collect(command, timeout=timeout)
        if not responses:
            raise DatoubossProtocolError("No response from inverter")
        return responses

    async def send_command(
        self,
        command: str,
        *,
        expect_response: bool = True,
        timeout: int | None = None,
    ) -> CommandResponse:
        if not expect_response:
            frame = DatoubossTcpClient.build_frame(command)
            loop = asyncio.get_running_loop()
            async with self._lock:
                try:
                    await loop.run_in_executor(None, self._ensure_open)
                    await loop.run_in_executor(None, self._write_frame, frame)
                except (OSError, serial.SerialException) as err:
                    await loop.run_in_executor(None, self._drop)
                    raise DatoubossConnectionError(
                        f"Serial failure while sending {command}"
                    ) from err
            return CommandResponse(
                command=command,
                raw_frame_hex=frame.hex(" "),
                raw_payload="",
                crc_ok=True,
            )

        responses = await self._send_and_collect(command, timeout=timeout)
        if not responses:
            raise DatoubossProtocolError("No response from inverter")

        response = DatoubossTcpClient.find_matching_response(command, responses)
        if response is None:
            if not command.startswith("Q") and not command.startswith("H"):
                raise DatoubossProtocolError(
                    f"No ACK/NAK response received for write command {command}"
                )
            response = responses[0]

        if command == "QMN":
            model = response.raw_payload.lstrip("(").strip()
            self._model_name = model or None
            if (
                self._configured_protocol == PROTOCOL_AUTO
                and self._detected_protocol is None
            ):
                self._detected_protocol = (
                    PROTOCOL_VMII
                    if model.upper().startswith("VMII-")
                    else PROTOCOL_CLASSIC
                )

        if response.raw_payload.startswith("(NAK"):
            raise DatoubossCommandError(
                f"Inverter rejected command {command}: {response.raw_payload}"
            )
        return response

    async def ensure_protocol(self) -> str:
        """Resolve the protocol variant. Tries QA6248 first via QPRTL."""
        if self._configured_protocol != PROTOCOL_AUTO:
            return self._configured_protocol
        if self._detected_protocol is not None:
            return self._detected_protocol

        try:
            await self.send_command("QPRTL")
            self._detected_protocol = PROTOCOL_QA6248
            _LOGGER.info("Detected QA6248 protocol via serial (QPRTL)")
            return self._detected_protocol
        except DatoubossError:
            _LOGGER.debug("QPRTL failed, falling back to legacy Voltronic")

        try:
            model = (await self.send_command("QMN")).raw_payload.lstrip("(").strip()
        except DatoubossError:
            self._detected_protocol = PROTOCOL_CLASSIC
            return self._detected_protocol

        self._model_name = model or None
        self._detected_protocol = (
            PROTOCOL_VMII if model.upper().startswith("VMII-") else PROTOCOL_CLASSIC
        )
        return self._detected_protocol

    async def fetch_supported_currents(self, command: str) -> list[int]:
        response = await self.send_command(command)
        return [
            int(chunk)
            for chunk in response.raw_payload.lstrip("(").split()
            if chunk.isdigit()
        ]

    async def probe(self) -> dict[str, Any]:
        """Probe the inverter and return basic information."""
        await self.ensure_protocol()

        if self._detected_protocol == PROTOCOL_QA6248:
            try:
                hsts = await self.send_command("HSTS")
                text = hsts.raw_payload.lstrip("(").strip()
                parts = text.split()
                mode = parts[1][0] if len(parts) > 1 and parts[1] else "X"
            except DatoubossError:
                mode = "X"
            return {
                "serial": self._model_name or "QA6248",
                "mode": mode,
                "model_name": self._model_name,
                "protocol_variant": self.protocol_variant,
            }

        serial_payload = (await self.send_command("QID")).raw_payload.lstrip("(")
        serial_number = re.sub(r"\D", "", serial_payload) or serial_payload
        mode = (await self.send_command("QMOD")).raw_payload.lstrip("(")
        return {
            "serial": serial_number,
            "mode": mode,
            "model_name": self._model_name,
            "protocol_variant": self.protocol_variant,
        }