"""IOKit ctypes wrapper for macOS power management."""

import ctypes
import ctypes.util
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Types
CFTypeRef = ctypes.c_void_p
CFArrayRef = ctypes.c_void_p
CFDictionaryRef = ctypes.c_void_p
CFStringRef = ctypes.c_void_p
CFNumberRef = ctypes.c_void_p
CFBooleanRef = ctypes.c_void_p
CFIndex = ctypes.c_long
CFStringEncoding = ctypes.c_uint32

kCFStringEncodingUTF8 = 0x08000100
kCFNumberIntType = 9
kCFNumberFloatType = 12
kCFNumberDoubleType = 13


class IOKitLib:
    """Wrapper for IOKit and CoreFoundation libraries."""

    def __init__(self) -> None:
        self._cf: Any = None  # ctypes CDLL once loaded
        self._iokit: Any = None  # ctypes CDLL once loaded
        self._loaded = False
        self._load_libraries()

    def _load_libraries(self) -> None:
        try:
            cf_path = ctypes.util.find_library("CoreFoundation")
            iokit_path = ctypes.util.find_library("IOKit")

            if not cf_path or not iokit_path:
                logger.debug("CoreFoundation or IOKit not found")
                return

            self._cf = ctypes.cdll.LoadLibrary(cf_path)
            self._iokit = ctypes.cdll.LoadLibrary(iokit_path)

            # setup signatures
            self._setup_cf_signatures()
            self._setup_iokit_signatures()

            self._loaded = True
        except Exception as e:
            logger.error(f"Failed to load IOKit libraries: {e}")

    def _setup_cf_signatures(self) -> None:
        # CFRelease
        self._cf.CFRelease.argtypes = [CFTypeRef]
        self._cf.CFRelease.restype = None

        # CFStringCreateWithCString
        self._cf.CFStringCreateWithCString.argtypes = [CFTypeRef, ctypes.c_char_p, CFStringEncoding]
        self._cf.CFStringCreateWithCString.restype = CFStringRef

        # CFArrayGetCount
        self._cf.CFArrayGetCount.argtypes = [CFArrayRef]
        self._cf.CFArrayGetCount.restype = CFIndex

        # CFArrayGetValueAtIndex
        self._cf.CFArrayGetValueAtIndex.argtypes = [CFArrayRef, CFIndex]
        self._cf.CFArrayGetValueAtIndex.restype = CFTypeRef

        # CFDictionaryGetValue
        self._cf.CFDictionaryGetValue.argtypes = [CFDictionaryRef, CFTypeRef]
        self._cf.CFDictionaryGetValue.restype = CFTypeRef

        # CFNumberGetValue
        self._cf.CFNumberGetValue.argtypes = [CFNumberRef, ctypes.c_long, ctypes.c_void_p]
        self._cf.CFNumberGetValue.restype = ctypes.c_bool

        # CFBooleanGetValue
        self._cf.CFBooleanGetValue.argtypes = [CFBooleanRef]
        self._cf.CFBooleanGetValue.restype = ctypes.c_bool

    def _setup_iokit_signatures(self) -> None:
        # IOPSCopyPowerSourcesInfo
        self._iokit.IOPSCopyPowerSourcesInfo.argtypes = []
        self._iokit.IOPSCopyPowerSourcesInfo.restype = CFTypeRef

        # IOPSCopyPowerSourcesList
        self._iokit.IOPSCopyPowerSourcesList.argtypes = [CFTypeRef]
        self._iokit.IOPSCopyPowerSourcesList.restype = CFArrayRef

        # IOPSGetPowerSourceDescription
        self._iokit.IOPSGetPowerSourceDescription.argtypes = [CFTypeRef, CFTypeRef]
        self._iokit.IOPSGetPowerSourceDescription.restype = CFDictionaryRef

    @property
    def available(self) -> bool:
        return self._loaded

    def get_power_sources_info(self) -> dict[str, Any]:
        """Get power sources info as a python dict."""
        if not self.available:
            return {}

        blob = self._iokit.IOPSCopyPowerSourcesInfo()
        if not blob:
            return {}

        sources_list = self._iokit.IOPSCopyPowerSourcesList(blob)
        if not sources_list:
            self._cf.CFRelease(blob)
            return {}

        count = self._cf.CFArrayGetCount(sources_list)
        result: dict[str, list[dict[str, Any]]] = {"sources": []}

        try:
            for i in range(count):
                source_blob = self._cf.CFArrayGetValueAtIndex(sources_list, i)
                desc_dict = self._iokit.IOPSGetPowerSourceDescription(blob, source_blob)

                # Extract values
                source_info = {
                    "current_capacity": self._get_dict_int(desc_dict, "Current Capacity"),
                    "max_capacity": self._get_dict_int(desc_dict, "Max Capacity"),
                    "voltage": self._get_dict_double(desc_dict, "Voltage"),
                    "is_charging": self._get_dict_bool(desc_dict, "Is Charging"),
                    "time_remaining": self._get_dict_int(desc_dict, "Time to Empty"),
                    "transport_type": "Internal",  # Simplification
                }
                result["sources"].append(source_info)

        finally:
            self._cf.CFRelease(sources_list)
            self._cf.CFRelease(blob)

        return result

    def _create_cf_string(self, s: str) -> CFStringRef:
        return self._cf.CFStringCreateWithCString(None, s.encode("utf-8"), kCFStringEncodingUTF8)

    def _get_dict_value(self, dictionary: CFDictionaryRef, key: str) -> CFTypeRef | None:
        k = self._create_cf_string(key)
        val = self._cf.CFDictionaryGetValue(dictionary, k)
        self._cf.CFRelease(k)
        return val

    def _get_dict_int(self, dictionary: CFDictionaryRef, key: str) -> int:
        val_ref = self._get_dict_value(dictionary, key)
        if not val_ref:
            return 0

        value = ctypes.c_int(0)
        self._cf.CFNumberGetValue(val_ref, kCFNumberIntType, ctypes.byref(value))
        return value.value

    def _get_dict_double(self, dictionary: CFDictionaryRef, key: str) -> float:
        val_ref = self._get_dict_value(dictionary, key)
        if not val_ref:
            return 0.0

        value = ctypes.c_double(0.0)
        self._cf.CFNumberGetValue(val_ref, kCFNumberDoubleType, ctypes.byref(value))
        return value.value

    def _get_dict_bool(self, dictionary: CFDictionaryRef, key: str) -> bool:
        val_ref = self._get_dict_value(dictionary, key)
        if not val_ref:
            return False
        return self._cf.CFBooleanGetValue(val_ref)
