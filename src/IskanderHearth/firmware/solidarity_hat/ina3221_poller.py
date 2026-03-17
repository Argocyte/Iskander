#!/usr/bin/env python3
"""
ina3221_poller.py — INA3221 Low-Level I2C Polling Module

License: CERN-OHL-S v2 / MIT (software component)

Provides a thin wrapper around the TI INA3221AIDR three-channel power monitor
at I2C address 0x40. Used by permacomputing_monitor.py for graceful degradation.

INA3221 register map (relevant subset):
    0x00 — Configuration
    0x01 — CH1 Shunt Voltage
    0x02 — CH1 Bus Voltage
    0x03 — CH2 Shunt Voltage
    0x04 — CH2 Bus Voltage
    0x05 — CH3 Shunt Voltage
    0x06 — CH3 Bus Voltage
    0xFF — Die ID (should read 0x3220)

Dependencies:
    pip install smbus2
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

try:
    import smbus2
    SMBUS2_AVAILABLE = True
except ImportError:
    SMBUS2_AVAILABLE = False

log = logging.getLogger("hearth.ina3221")

# ── Constants ─────────────────────────────────────────────────────────────────

INA3221_I2C_ADDR    = 0x40          # A0=GND A1=GND
INA3221_DIE_ID      = 0x3220        # Expected value from register 0xFF
INA3221_REG_CONFIG  = 0x00
INA3221_REG_DIE_ID  = 0xFF

# Channel register base addresses: shunt = base, bus = base+1
_CH_SHUNT_REG = {1: 0x01, 2: 0x03, 3: 0x05}
_CH_BUS_REG   = {1: 0x02, 2: 0x04, 3: 0x06}

# Shunt resistance on HAT (0.1Ω, see BOM MISC-7f / P5-007f)
SHUNT_RESISTANCE_OHMS = 0.1

# INA3221 LSB values per datasheet:
#   Shunt voltage: 40 µV/LSB
#   Bus voltage:    8 mV/LSB
SHUNT_VOLTAGE_LSB_UV = 40.0    # microvolts
BUS_VOLTAGE_LSB_MV   = 8.0     # millivolts


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ChannelReading:
    channel: int
    bus_voltage_v: float    # Volts
    shunt_voltage_mv: float # Millivolts
    current_ma: float       # Milliamps (derived from shunt / R)
    power_mw: float         # Milliwatts (V * I)
    timestamp: float        # Unix timestamp

    @classmethod
    def from_raw(
        cls,
        channel: int,
        raw_bus: int,
        raw_shunt: int,
        timestamp: float,
    ) -> "ChannelReading":
        # Bus voltage: 13-bit, bits [15:3], 8mV LSB
        bus_v = ((raw_bus >> 3) & 0x1FFF) * (BUS_VOLTAGE_LSB_MV / 1000.0)
        # Shunt voltage: 13-bit signed two's complement, 40µV LSB
        shunt_raw = raw_shunt >> 3
        if shunt_raw & 0x1000:  # sign bit
            shunt_raw -= 0x2000
        shunt_mv = shunt_raw * (SHUNT_VOLTAGE_LSB_UV / 1000.0)
        current_ma = (shunt_mv / 1000.0) / SHUNT_RESISTANCE_OHMS * 1000.0
        power_mw = bus_v * current_ma
        return cls(
            channel=channel,
            bus_voltage_v=round(bus_v, 4),
            shunt_voltage_mv=round(shunt_mv, 4),
            current_ma=round(current_ma, 3),
            power_mw=round(power_mw, 3),
            timestamp=timestamp,
        )


@dataclass
class PowerSnapshot:
    """All three channel readings at one sample instant."""
    ch1: ChannelReading  # 12V system rail
    ch2: ChannelReading  # Solar/battery rail
    ch3: ChannelReading  # 3.3V auxiliary rail
    timestamp: float

    def solar_battery_voltage(self) -> float:
        """Convenience: CH2 bus voltage — primary energy source monitor."""
        return self.ch2.bus_voltage_v


# ── INA3221 driver ────────────────────────────────────────────────────────────

class INA3221:
    """
    Minimal driver for TI INA3221AIDR on the Solidarity HAT.

    Raises RuntimeError on init if:
    - smbus2 is not installed
    - I2C device not found at expected address
    - Die ID register returns unexpected value (wrong chip or communication error)

    All failures must be treated as hardware compromise. See FAILURE POLICY in
    permacomputing_monitor.py.
    """

    def __init__(self, i2c_bus: int = 1, address: int = INA3221_I2C_ADDR) -> None:
        if not SMBUS2_AVAILABLE:
            raise RuntimeError(
                "smbus2 not installed. Run: pip install smbus2\n"
                "The Solidarity HAT power monitoring subsystem is non-functional."
            )
        self._bus_num = i2c_bus
        self._addr    = address
        self._bus: Optional[smbus2.SMBus] = None
        self._init()

    def _init(self) -> None:
        """Open I2C bus and verify chip identity."""
        try:
            self._bus = smbus2.SMBus(self._bus_num)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot open I2C bus {self._bus_num}: {exc}"
            ) from exc

        try:
            die_id = self._read_register(INA3221_REG_DIE_ID)
        except Exception as exc:
            raise RuntimeError(
                f"INA3221 not responding at I2C 0x{self._addr:02X}: {exc}"
            ) from exc

        if die_id != INA3221_DIE_ID:
            raise RuntimeError(
                f"INA3221 Die ID mismatch: expected 0x{INA3221_DIE_ID:04X}, "
                f"got 0x{die_id:04X}. Wrong chip or I2C corruption."
            )

        # Configure: all 3 channels enabled, 1.1ms conversion, 16 averages
        # Config register: [15:14]=11 (all CH enabled) [13:11]=100 (1.1ms) [10:8]=100 (1.1ms) [7:3]=111 (16 avg) [2:0]=111 (all enabled)
        # Using safe reset value (0x7127) as starting point
        self._write_register(INA3221_REG_CONFIG, 0x7127)
        log.info(
            "INA3221 initialized at I2C 0x%02X on bus %d.", self._addr, self._bus_num
        )

    def _read_register(self, reg: int) -> int:
        """Read a 16-bit big-endian register."""
        assert self._bus is not None
        data = self._bus.read_i2c_block_data(self._addr, reg, 2)
        return (data[0] << 8) | data[1]

    def _write_register(self, reg: int, value: int) -> None:
        """Write a 16-bit big-endian register."""
        assert self._bus is not None
        self._bus.write_i2c_block_data(
            self._addr, reg, [(value >> 8) & 0xFF, value & 0xFF]
        )

    def read_channel(self, channel: int) -> ChannelReading:
        """
        Read a single channel (1, 2, or 3).

        Returns a ChannelReading with bus voltage, shunt voltage, current, power.
        """
        if channel not in (1, 2, 3):
            raise ValueError(f"Invalid channel {channel}: must be 1, 2, or 3.")
        ts = time.time()
        raw_shunt = self._read_register(_CH_SHUNT_REG[channel])
        raw_bus   = self._read_register(_CH_BUS_REG[channel])
        return ChannelReading.from_raw(channel, raw_bus, raw_shunt, ts)

    def read_all(self) -> PowerSnapshot:
        """Read all three channels and return a PowerSnapshot."""
        ts   = time.time()
        ch1  = self.read_channel(1)
        ch2  = self.read_channel(2)
        ch3  = self.read_channel(3)
        return PowerSnapshot(ch1=ch1, ch2=ch2, ch3=ch3, timestamp=ts)

    def close(self) -> None:
        """Release I2C bus handle."""
        if self._bus:
            self._bus.close()
            self._bus = None


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sensor = INA3221()
    print("\n── INA3221 Power Snapshot ──────────────────────")
    snap = sensor.read_all()
    for ch in (snap.ch1, snap.ch2, snap.ch3):
        labels = {1: "12V System", 2: "Solar/Batt", 3: "3.3V Aux"}
        print(
            f"  CH{ch.channel} [{labels[ch.channel]}]  "
            f"{ch.bus_voltage_v:.4f}V  {ch.current_ma:.1f}mA  {ch.power_mw:.1f}mW"
        )
    print(f"  Solar/Battery voltage: {snap.solar_battery_voltage():.4f}V")
    sensor.close()
