"""Common Windows types and structures.

Centralized ctypes structures used across Windows HAL adapters.
Import from here to avoid duplication.

Created: December 25, 2025
"""

from __future__ import annotations

import ctypes


class SYSTEM_POWER_STATUS(ctypes.Structure):
    """Windows SYSTEM_POWER_STATUS structure.

    Used by GetSystemPowerStatus to retrieve battery and power state.

    Fields:
        ACLineStatus: 0 = offline, 1 = online, 255 = unknown
        BatteryFlag: Bitmask of battery status flags
        BatteryLifePercent: 0-100 or 255 if unknown
        Reserved1: Reserved, must be zero
        BatteryLifeTime: Seconds of battery life remaining, or -1 if unknown
        BatteryFullLifeTime: Seconds of battery life when full, or -1 if unknown
    """

    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("Reserved1", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    """Windows BITMAPINFOHEADER structure.

    Used for DIB (Device-Independent Bitmap) operations.
    """

    _fields_ = [
        ("biSize", ctypes.c_ulong),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", ctypes.c_ulong),
        ("biSizeImage", ctypes.c_ulong),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_ulong),
        ("biClrImportant", ctypes.c_ulong),
    ]


class RGBQUAD(ctypes.Structure):
    """Windows RGBQUAD structure for color palette."""

    _fields_ = [
        ("rgbBlue", ctypes.c_byte),
        ("rgbGreen", ctypes.c_byte),
        ("rgbRed", ctypes.c_byte),
        ("rgbReserved", ctypes.c_byte),
    ]


class BITMAPINFO(ctypes.Structure):
    """Windows BITMAPINFO structure."""

    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


__all__ = [
    "BITMAPINFO",
    "BITMAPINFOHEADER",
    "RGBQUAD",
    "SYSTEM_POWER_STATUS",
]
