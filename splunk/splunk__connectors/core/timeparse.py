"""
Turn whatever a source calls a timestamp into the epoch seconds HEC wants.

HEC accepts a numeric "time" and rejects anything else with code 6, and the
rejection takes the whole batch, not the offending event. The ePO export
writes ISO 8601 with milliseconds and a Z suffix, so a connector that passes
its time column through unchanged loses every event in every batch.

Failure is a third outcome, never a guess. An unparseable value yields None,
the caller omits "time" so Splunk applies index time, and the raw value is
carried on the event as time_raw - a timestamp that could not be read must
stay visible rather than become a plausible wrong number.
"""

from datetime import datetime, timezone

# Ordered by how often the estate produces them. %f accepts 1-6 digits, so one
# entry covers milliseconds and microseconds alike.
_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",
    "%Y-%m-%d",
)

# Below this, a number is far more likely to be a count than a date: 10^9 is
# 2001-09-09, and every timestamp this software will see is later.
_EPOCH_FLOOR = 1_000_000_000


def to_epoch(value):
    """Return epoch seconds as a float, or None when the value is not a time.

    A bare number is taken as epoch seconds, or milliseconds when it is large
    enough that seconds would put it centuries into the future.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _scale(float(value))

    text = str(value).strip()
    if not text:
        return None

    try:
        number = float(text)
    except ValueError:
        pass
    else:
        return _scale(number)

    # Python accepts "+00:00" but not the "Z" the exporter writes.
    normalized = text[:-1] + "+0000" if text.endswith("Z") else text
    # %z takes "+0000" but not "+00:00" before 3.7, and colons are common.
    if len(normalized) > 6 and normalized[-3] == ":" and normalized[-6] in "+-":
        normalized = normalized[:-3] + normalized[-2:]

    for fmt in _FORMATS:
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _scale(number):
    """Epoch seconds, converting from milliseconds when the magnitude says so."""
    if abs(number) >= _EPOCH_FLOOR * 1000:
        return number / 1000.0
    if 0 < abs(number) < _EPOCH_FLOOR:
        # Too small to be a date. A duration or a row counter reaching this
        # function is a mapping error, and inventing 1970 would hide it.
        return None
    return number
