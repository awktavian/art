"""Common trigger condition helpers.

CREATED: January 5, 2026
"""

import datetime
from collections.abc import Callable


def time_window(start_hour: int, end_hour: int) -> Callable[[dict], bool]:
    """Create condition that checks if current time is in window.

    Args:
        start_hour: Start hour (0-23)
        end_hour: End hour (0-23)

    Returns:
        Condition function

    Example:
        >>> morning = time_window(6, 10)
        >>> morning({})  # True if 6 AM - 10 AM
    """

    def check(data: dict) -> bool:
        now = datetime.datetime.now()
        return start_hour <= now.hour < end_hour

    return check


def temperature_threshold(
    min_temp: float | None = None, max_temp: float | None = None, feels_like: bool = False
) -> Callable[[dict], bool]:
    """Create condition that checks temperature threshold.

    Args:
        min_temp: Minimum temperature (F)
        max_temp: Maximum temperature (F)
        feels_like: Use feels_like_f instead of temp_f

    Returns:
        Condition function

    Example:
        >>> cold = temperature_threshold(max_temp=45, feels_like=True)
        >>> cold({"feels_like_f": 40})  # True
    """

    def check(data: dict) -> bool:
        temp_key = "feels_like_f" if feels_like else "temp_f"
        temp = data.get(temp_key, data.get("temp_f", 70))

        if min_temp is not None and temp < min_temp:
            return False
        if max_temp is not None and temp > max_temp:
            return False

        return True

    return check


def significant_change(
    key: str, threshold: float, state_dict: dict, *, absolute: bool = True
) -> Callable[[dict], bool]:
    """Create condition that detects significant changes.

    Args:
        key: Data key to monitor
        threshold: Change threshold
        state_dict: Shared state dict to store last value
        absolute: Use absolute difference (vs percentage)

    Returns:
        Condition function

    Example:
        >>> last_temp = {}
        >>> temp_changed = significant_change("temp_f", 10, last_temp)
        >>> temp_changed({"temp_f": 50})  # True (first time)
        >>> temp_changed({"temp_f": 52})  # False (only 2°)
        >>> temp_changed({"temp_f": 62})  # True (12° change)
    """

    def check(data: dict) -> bool:
        current = data.get(key)
        if current is None:
            return False

        # First time - store and don't trigger
        if key not in state_dict:
            state_dict[key] = current
            return False

        last = state_dict[key]

        # Calculate change
        if absolute:
            change = abs(current - last)
            significant = change >= threshold
        else:
            # Percentage change
            if last == 0:
                significant = current != 0
            else:
                pct_change = abs((current - last) / last)
                significant = pct_change >= threshold

        # Update state if significant
        if significant:
            state_dict[key] = current

        return significant

    return check


def keyword_match(*keywords: str, case_sensitive: bool = False) -> Callable[[dict], bool]:
    """Create condition that matches keywords in text.

    Args:
        *keywords: Keywords to match
        case_sensitive: Whether to match case

    Returns:
        Condition function

    Example:
        >>> urgent = keyword_match("urgent", "asap", "critical")
        >>> urgent({"text": "This is URGENT!"})  # True
    """

    def check(data: dict) -> bool:
        text = data.get("text", "")
        if not text:
            return False

        if not case_sensitive:
            text = text.lower()
            keywords_check = [k.lower() for k in keywords]
        else:
            keywords_check = list(keywords)

        return any(kw in text for kw in keywords_check)

    return check


def combine_and(*conditions: Callable[[dict], bool]) -> Callable[[dict], bool]:
    """Combine multiple conditions with AND logic.

    Args:
        *conditions: Conditions to combine

    Returns:
        Combined condition function

    Example:
        >>> morning_cold = combine_and(
        ...     time_window(6, 10),
        ...     temperature_threshold(max_temp=40)
        ... )
    """

    def check(data: dict) -> bool:
        return all(cond(data) for cond in conditions)

    return check


def combine_or(*conditions: Callable[[dict], bool]) -> Callable[[dict], bool]:
    """Combine multiple conditions with OR logic.

    Args:
        *conditions: Conditions to combine

    Returns:
        Combined condition function

    Example:
        >>> important = combine_or(
        ...     keyword_match("urgent", "critical"),
        ...     lambda d: d.get("priority") == "high"
        ... )
    """

    def check(data: dict) -> bool:
        return any(cond(data) for cond in conditions)

    return check
