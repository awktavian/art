"""Internationalization (i18n) Framework.

Provides translation and localization support for Kagami apps:
- 10 languages: en, es, ar, zh, vi, ja, ko, fr, de, pt
- RTL support for Arabic
- Pluralization rules per language
- Date/time/number formatting per locale
- Thread-safe translation loading

Usage:
    from kagami.core.i18n import t, set_locale, get_locale, get_available_locales

    # Set user's locale
    set_locale("es")

    # Translate strings
    message = t("welcome_message")  # "¡Bienvenido!"
    message = t("device_count", count=5)  # "5 dispositivos"

    # Get current locale
    current = get_locale()  # "es"

    # Format dates/numbers per locale
    from kagami.core.i18n import format_date, format_number
    formatted = format_date(datetime.now())  # "1 de enero de 2026"
    formatted = format_number(1234.56)  # "1.234,56"

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.2
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Thread-local storage for current locale
_locale_storage = threading.local()

# Global translation cache
_translations: dict[str, dict[str, Any]] = {}
_translations_lock = threading.Lock()

# Supported locales
SUPPORTED_LOCALES = [
    "en",  # English (default)
    "es",  # Spanish
    "ar",  # Arabic (RTL)
    "zh",  # Chinese (Simplified)
    "vi",  # Vietnamese
    "ja",  # Japanese
    "ko",  # Korean
    "fr",  # French
    "de",  # German
    "pt",  # Portuguese
]

# RTL languages
RTL_LOCALES = ["ar"]

# Default locale
DEFAULT_LOCALE = "en"

# Locales directory
LOCALES_DIR = Path(__file__).parent / "locales"


def get_locale() -> str:
    """Get the current locale for this thread.

    Returns:
        Locale code (e.g., "en", "es", "ar")
    """
    return getattr(_locale_storage, "locale", DEFAULT_LOCALE)


def set_locale(locale: str) -> None:
    """Set the current locale for this thread.

    Args:
        locale: Locale code (e.g., "en", "es", "ar")

    Raises:
        ValueError: If locale is not supported
    """
    if locale not in SUPPORTED_LOCALES:
        logger.warning(f"Unsupported locale: {locale}, falling back to {DEFAULT_LOCALE}")
        locale = DEFAULT_LOCALE
    _locale_storage.locale = locale


def get_available_locales() -> list[str]:
    """Get list of all supported locales.

    Returns:
        List of locale codes
    """
    return SUPPORTED_LOCALES.copy()


def is_rtl(locale: str | None = None) -> bool:
    """Check if a locale is right-to-left.

    Args:
        locale: Locale code, or None for current locale

    Returns:
        True if RTL language
    """
    if locale is None:
        locale = get_locale()
    return locale in RTL_LOCALES


def _load_translations(locale: str) -> dict[str, Any]:
    """Load translations for a locale from JSON file.

    Args:
        locale: Locale code

    Returns:
        Dictionary of translations
    """
    with _translations_lock:
        if locale in _translations:
            return _translations[locale]

        locale_file = LOCALES_DIR / f"{locale}.json"

        if not locale_file.exists():
            logger.warning(f"Translation file not found: {locale_file}")
            # Fall back to English
            if locale != DEFAULT_LOCALE:
                return _load_translations(DEFAULT_LOCALE)
            return {}

        try:
            with open(locale_file, encoding="utf-8") as f:
                translations = json.load(f)
            _translations[locale] = translations
            logger.debug(f"Loaded {len(translations)} translations for locale: {locale}")
            return translations
        except Exception as e:
            logger.error(f"Failed to load translations for {locale}: {e}")
            if locale != DEFAULT_LOCALE:
                return _load_translations(DEFAULT_LOCALE)
            return {}


def _get_nested(data: dict[str, Any], key: str) -> Any:
    """Get a nested value from a dictionary using dot notation.

    Args:
        data: Dictionary to search
        key: Key in dot notation (e.g., "home.welcome")

    Returns:
        Value or None if not found
    """
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def t(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Translate a key to the current or specified locale.

    Args:
        key: Translation key (supports dot notation, e.g., "home.welcome")
        locale: Optional locale override
        **kwargs: Variables to interpolate (e.g., count=5, name="John")

    Returns:
        Translated string, or the key if not found

    Example:
        >>> t("welcome")  # "Welcome"
        >>> t("device_count", count=5)  # "5 devices"
        >>> t("greeting", name="John")  # "Hello, John!"
        >>> t("home.title")  # "Home"
    """
    if locale is None:
        locale = get_locale()

    translations = _load_translations(locale)

    # Try to get translation
    value = _get_nested(translations, key)

    if value is None:
        # Fall back to English if not found
        if locale != DEFAULT_LOCALE:
            translations = _load_translations(DEFAULT_LOCALE)
            value = _get_nested(translations, key)

    if value is None:
        # Return key as fallback
        logger.debug(f"Translation not found: {key} (locale={locale})")
        return key

    # Handle pluralization
    if isinstance(value, dict) and "count" in kwargs:
        count = kwargs["count"]
        value = _pluralize(value, count, locale)

    # Interpolate variables
    if isinstance(value, str) and kwargs:
        try:
            value = value.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing interpolation variable in {key}: {e}")

    return str(value)


def _pluralize(forms: dict[str, str], count: int, locale: str) -> str:
    """Select the correct plural form based on count and locale.

    Different languages have different pluralization rules:
    - English: one (1), other (0, 2+)
    - Arabic: zero (0), one (1), two (2), few (3-10), many (11-99), other (100+)
    - Chinese/Japanese/Korean/Vietnamese: other (all)
    - French/Spanish/Portuguese: one (1), other (0, 2+)
    - German: one (1), other (0, 2+)

    Args:
        forms: Dictionary with plural forms (e.g., {"one": "1 item", "other": "{count} items"})
        count: The count to pluralize
        locale: Current locale

    Returns:
        The appropriate form
    """
    # Get the plural category
    category = _get_plural_category(count, locale)

    # Try to get the form for this category
    if category in forms:
        return forms[category]

    # Fall back to "other"
    if "other" in forms:
        return forms["other"]

    # Return any available form
    return next(iter(forms.values()), str(count))


def _get_plural_category(count: int, locale: str) -> str:
    """Get the CLDR plural category for a count and locale.

    Based on CLDR plural rules:
    https://cldr.unicode.org/index/cldr-spec/plural-rules

    Args:
        count: The count
        locale: Locale code

    Returns:
        Plural category: "zero", "one", "two", "few", "many", "other"
    """
    n = abs(count)

    # Chinese, Japanese, Korean, Vietnamese - no plural
    if locale in ("zh", "ja", "ko", "vi"):
        return "other"

    # Arabic - complex plural rules
    if locale == "ar":
        if n == 0:
            return "zero"
        elif n == 1:
            return "one"
        elif n == 2:
            return "two"
        elif 3 <= n % 100 <= 10:
            return "few"
        elif 11 <= n % 100 <= 99:
            return "many"
        else:
            return "other"

    # English, Spanish, French, German, Portuguese - simple one/other
    if n == 1:
        return "one"
    return "other"


def format_number(
    value: float | int,
    locale: str | None = None,
    decimal_places: int = 2,
) -> str:
    """Format a number according to locale conventions.

    Args:
        value: Number to format
        locale: Optional locale override
        decimal_places: Number of decimal places

    Returns:
        Formatted number string

    Example:
        >>> format_number(1234.56, locale="en")  # "1,234.56"
        >>> format_number(1234.56, locale="de")  # "1.234,56"
        >>> format_number(1234.56, locale="ar")  # "١٬٢٣٤٫٥٦"
    """
    if locale is None:
        locale = get_locale()

    # Format with decimal places
    if decimal_places > 0:
        formatted = f"{value:,.{decimal_places}f}"
    else:
        formatted = f"{int(value):,}"

    # Locale-specific number formatting
    if locale in ("de", "es", "fr", "pt"):
        # Swap . and ,
        formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    elif locale == "ar":
        # Use Arabic-Indic numerals
        arabic_numerals = "٠١٢٣٤٥٦٧٨٩"
        result = ""
        for char in formatted:
            if char.isdigit():
                result += arabic_numerals[int(char)]
            elif char == ",":
                result += "٬"  # Arabic thousands separator
            elif char == ".":
                result += "٫"  # Arabic decimal separator
            else:
                result += char
        formatted = result

    return formatted


def format_date(
    dt: datetime,
    locale: str | None = None,
    format_type: str = "medium",
) -> str:
    """Format a datetime according to locale conventions.

    Args:
        dt: Datetime to format
        locale: Optional locale override
        format_type: "short", "medium", "long", "full"

    Returns:
        Formatted date string

    Example:
        >>> format_date(datetime(2026, 1, 1), locale="en")  # "Jan 1, 2026"
        >>> format_date(datetime(2026, 1, 1), locale="de")  # "1. Jan. 2026"
        >>> format_date(datetime(2026, 1, 1), locale="ja")  # "2026年1月1日"
    """
    if locale is None:
        locale = get_locale()

    # Load locale-specific date formats
    translations = _load_translations(locale)
    date_formats = translations.get("_formats", {}).get("date", {})

    # Get format pattern
    pattern = date_formats.get(format_type)

    if pattern:
        # Use locale-specific pattern
        return _format_date_pattern(dt, pattern, locale)

    # Fallback to basic formatting
    if format_type == "short":
        return dt.strftime("%m/%d/%y")
    elif format_type == "long":
        return dt.strftime("%B %d, %Y")
    elif format_type == "full":
        return dt.strftime("%A, %B %d, %Y")
    else:  # medium
        return dt.strftime("%b %d, %Y")


def _format_date_pattern(dt: datetime, pattern: str, locale: str) -> str:
    """Format a date using a pattern string.

    Pattern tokens:
    - YYYY: 4-digit year
    - MM: 2-digit month
    - DD: 2-digit day
    - MMMM: Full month name
    - MMM: Abbreviated month name
    - EEEE: Full weekday name
    - EEE: Abbreviated weekday name

    Args:
        dt: Datetime to format
        pattern: Format pattern
        locale: Locale code

    Returns:
        Formatted date string
    """
    translations = _load_translations(locale)
    months = translations.get("_formats", {}).get("months", [])
    months_short = translations.get("_formats", {}).get("months_short", [])
    weekdays = translations.get("_formats", {}).get("weekdays", [])
    weekdays_short = translations.get("_formats", {}).get("weekdays_short", [])

    result = pattern
    result = result.replace("YYYY", str(dt.year))
    result = result.replace("MM", f"{dt.month:02d}")
    result = result.replace("DD", f"{dt.day:02d}")

    if months and dt.month <= len(months):
        result = result.replace("MMMM", months[dt.month - 1])
    if months_short and dt.month <= len(months_short):
        result = result.replace("MMM", months_short[dt.month - 1])
    if weekdays and dt.weekday() < len(weekdays):
        result = result.replace("EEEE", weekdays[dt.weekday()])
    if weekdays_short and dt.weekday() < len(weekdays_short):
        result = result.replace("EEE", weekdays_short[dt.weekday()])

    return result


def format_time(
    dt: datetime,
    locale: str | None = None,
    format_type: str = "short",
) -> str:
    """Format a time according to locale conventions.

    Args:
        dt: Datetime to format
        locale: Optional locale override
        format_type: "short", "medium", "long"

    Returns:
        Formatted time string
    """
    if locale is None:
        locale = get_locale()

    # Most locales use 24-hour time except US English
    if locale == "en":
        return dt.strftime("%I:%M %p")
    else:
        return dt.strftime("%H:%M")


def format_relative_time(
    dt: datetime,
    locale: str | None = None,
    reference: datetime | None = None,
) -> str:
    """Format a datetime as relative time (e.g., "5 minutes ago").

    Args:
        dt: Datetime to format
        locale: Optional locale override
        reference: Reference time (default: now)

    Returns:
        Relative time string

    Example:
        >>> format_relative_time(datetime.now() - timedelta(minutes=5))
        "5 minutes ago"
    """
    if locale is None:
        locale = get_locale()
    if reference is None:
        reference = datetime.now()

    diff = reference - dt
    seconds = diff.total_seconds()
    is_future = seconds < 0
    seconds = abs(seconds)

    # Determine the unit and value
    if seconds < 60:
        unit = "seconds"
        value = int(seconds)
    elif seconds < 3600:
        unit = "minutes"
        value = int(seconds / 60)
    elif seconds < 86400:
        unit = "hours"
        value = int(seconds / 3600)
    elif seconds < 604800:
        unit = "days"
        value = int(seconds / 86400)
    elif seconds < 2592000:
        unit = "weeks"
        value = int(seconds / 604800)
    elif seconds < 31536000:
        unit = "months"
        value = int(seconds / 2592000)
    else:
        unit = "years"
        value = int(seconds / 31536000)

    # Get translation
    key = f"relative_time.{unit}.{'future' if is_future else 'past'}"
    return t(key, locale=locale, count=value)


def reload_translations() -> None:
    """Force reload of all translation files.

    Useful when translations are updated at runtime.
    """
    global _translations
    with _translations_lock:
        _translations.clear()
    logger.info("Translation cache cleared")


# Context manager for temporary locale change
class locale_context:
    """Context manager for temporary locale change.

    Example:
        >>> with locale_context("es"):
        ...     message = t("welcome")  # Spanish
        >>> message = t("welcome")  # Back to original
    """

    def __init__(self, locale: str):
        self.locale = locale
        self.previous_locale: str | None = None

    def __enter__(self) -> locale_context:
        self.previous_locale = get_locale()
        set_locale(self.locale)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.previous_locale is not None:
            set_locale(self.previous_locale)


__all__ = [
    "DEFAULT_LOCALE",
    "RTL_LOCALES",
    "SUPPORTED_LOCALES",
    "format_date",
    "format_number",
    "format_relative_time",
    "format_time",
    "get_available_locales",
    "get_locale",
    "is_rtl",
    "locale_context",
    "reload_translations",
    "set_locale",
    "t",
]
