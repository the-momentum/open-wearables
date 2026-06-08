"""Minimal ANT+ FIT binary builder for test fixtures.

Builds valid FIT 2.0 files in memory with synthetic (non-real-user) data.
Field numbers and base types follow the ANT+ FIT Protocol specification.

Record message (global_mesg_num=20) fields used here:
  253  timestamp            uint32  (FIT epoch seconds)
    0  position_lat         sint32  (semicircles, no scale; parser converts to degrees)
    1  position_long        sint32  (semicircles, no scale)
    3  heart_rate           uint8   (bpm)
    4  cadence              uint8   (rpm)
    6  speed                uint16  (raw = m/s * 1000, fitdecode divides by scale=1000)
    7  power                uint16  (watts)
   13  temperature          sint8   (°C, no scale)
   39  vertical_oscillation uint16  (raw = mm * 10, fitdecode divides by scale=10 → mm)
   41  stance_time          uint16  (raw = ms * 10, fitdecode divides by scale=10 → ms)
   78  enhanced_altitude    uint32  (raw = (meters + 500) * 5, fitdecode → meters)
   83  vertical_ratio       uint16  (raw = % * 100, fitdecode divides by scale=100)
   84  stance_time_balance  uint16  (raw = % * 100, fitdecode divides by scale=100)
"""

import struct
from datetime import datetime, timezone
from typing import NamedTuple

# FIT epoch: 1989-12-31 00:00:00 UTC
_FIT_EPOCH_UNIX: int = 631065600

# Base type byte values used in definition messages
_SINT8: int = 0x01
_UINT8: int = 0x02
_UINT16: int = 0x84
_UINT32: int = 0x86
_SINT32: int = 0x85

# GPS: degrees × (2^31 / 180) = semicircles
_DEG_TO_SEMICIRCLES: float = 2**31 / 180

# FIT CRC table (from ANT+ FIT SDK)
_CRC_TABLE: tuple[int, ...] = (
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
)


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def _fit_ts(dt: datetime) -> int:
    return int(dt.timestamp()) - _FIT_EPOCH_UNIX


class _Field(NamedTuple):
    def_num: int
    base_type: int
    size: int


# Definition message: one record per layout (local_mesg_type=0, global=20)
def _definition_msg(fields: list[_Field]) -> bytes:
    header = 0x40  # definition, local_mesg_type=0
    # reserved(1) | architecture=LE(1) | global_mesg_num(2) | num_fields(1)
    body = struct.pack("<BBHB", 0x00, 0x00, 20, len(fields))
    for f in fields:
        body += struct.pack("BBB", f.def_num, f.size, f.base_type)
    return bytes([header]) + body


def _data_msg(fields: list[_Field], values: list[int]) -> bytes:
    header = 0x00  # data, local_mesg_type=0
    body = b""
    for f, v in zip(fields, values):
        signed = f.base_type in (_SINT8, _SINT32)
        if f.size == 1:
            body += struct.pack("<b" if signed else "<B", v)
        elif f.size == 2:
            body += struct.pack("<H", v)
        elif f.size == 4:
            body += struct.pack("<i" if signed else "<I", v)
    return bytes([header]) + body


def _fit_file(messages: bytes) -> bytes:
    data_size = len(messages)
    header_no_crc = struct.pack("<BBHI4s", 14, 0x20, 2132, data_size, b".FIT")
    header_crc = _crc16(header_no_crc)
    header = header_no_crc + struct.pack("<H", header_crc)
    file_crc = _crc16(messages)
    return header + messages + struct.pack("<H", file_crc)


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------


def make_running_fit(n_records: int = 20) -> bytes:
    """Synthetic running activity: full sensor set including GPS and running dynamics."""
    lat = int(50.0 * _DEG_TO_SEMICIRCLES)  # 50°N
    lon = int(20.0 * _DEG_TO_SEMICIRCLES)  # 20°E
    alt_raw = int((200.0 + 500) * 5)  # 200 m → raw enhanced_altitude

    fields = [
        _Field(253, _UINT32, 4),  # timestamp
        _Field(0, _SINT32, 4),  # position_lat (semicircles)
        _Field(1, _SINT32, 4),  # position_long (semicircles)
        _Field(3, _UINT8, 1),  # heart_rate
        _Field(4, _UINT8, 1),  # cadence
        _Field(6, _UINT16, 2),  # speed (raw = m/s * 1000)
        _Field(7, _UINT16, 2),  # power
        _Field(13, _SINT8, 1),  # temperature (°C)
        _Field(39, _UINT16, 2),  # vertical_oscillation (raw = mm * 10)
        _Field(41, _UINT16, 2),  # stance_time (raw = ms * 10)
        _Field(78, _UINT32, 4),  # enhanced_altitude (raw = (m + 500) * 5)
        _Field(83, _UINT16, 2),  # vertical_ratio (raw = % * 100)
        _Field(84, _UINT16, 2),  # stance_time_balance (raw = % * 100)
    ]
    start_ts = _fit_ts(datetime(2025, 6, 1, 8, 0, 0, tzinfo=timezone.utc))
    messages = _definition_msg(fields)
    for i in range(n_records):
        messages += _data_msg(
            fields,
            [
                start_ts + i,
                lat,
                lon,
                150 + i % 10,  # heart_rate: 150-159 bpm
                85,  # cadence: 85 rpm
                3200,  # speed: 3.2 m/s
                250,  # power: 250 W
                18,  # temperature: 18°C
                850,  # vertical_oscillation: 8.5 cm
                2400,  # stance_time: 240 ms
                alt_raw,  # enhanced_altitude: 200 m
                850,  # vertical_ratio: 8.5%
                4950,  # stance_time_balance: 49.5%
            ],
        )
    return _fit_file(messages)


def make_cycling_fit(n_records: int = 10) -> bytes:
    """Synthetic indoor cycling: HR only (no ANT+ sensors connected)."""
    fields = [
        _Field(253, _UINT32, 4),
        _Field(3, _UINT8, 1),
    ]
    start_ts = _fit_ts(datetime(2025, 6, 2, 10, 0, 0, tzinfo=timezone.utc))
    messages = _definition_msg(fields)
    for i in range(n_records):
        messages += _data_msg(fields, [start_ts + i, 160 + i % 5])
    return _fit_file(messages)


def make_swimming_fit(n_records: int = 10) -> bytes:
    """Synthetic lap swimming: HR only (GPS/cadence not available in water)."""
    fields = [
        _Field(253, _UINT32, 4),
        _Field(3, _UINT8, 1),
    ]
    start_ts = _fit_ts(datetime(2025, 6, 3, 7, 0, 0, tzinfo=timezone.utc))
    messages = _definition_msg(fields)
    for i in range(n_records):
        messages += _data_msg(fields, [start_ts + i, 140 + i % 8])
    return _fit_file(messages)
