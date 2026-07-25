"""Time calculation utilities for the scheduler."""

from datetime import datetime, timedelta, time as dt_time, timezone

# Slack subtracted from the due threshold so a tick that fires a few seconds shy
# of the exact interval (scheduler jitter) still counts the scan as due.
DUE_SLACK = timedelta(minutes=5)

# Offset subtracted from daily_notify_time so data is ready when the alert fires.
SCAN_LEAD_MINUTES = 10


def parse_hhmm(hhmm: str) -> dt_time:
    """Parse a ``HH:MM`` string into a :class:`datetime.time`.

    Args:
        hhmm: Time string in ``HH:MM`` format.

    Returns:
        Parsed :class:`datetime.time` (no tzinfo).
    """
    h, m = hhmm.split(":")
    return dt_time(int(h), int(m))


def is_scan_due(
    last_scan_at_iso: str | None, frequency_hours: int, now: datetime
) -> bool:
    """Whether a scan is due given the last-run time and configured frequency.
    
    Args:
        last_scan_at_iso: ISO-8601 timestamp of the last scan, or ``None`` if
            none has run yet.
        frequency_hours: Configured hours between scans.
        now: Reference "now" timestamp (timezone-aware).

    Returns:
        ``True`` when no scan has run yet or enough time has elapsed.
    """
    if not last_scan_at_iso:
        return True
    try:
        last = datetime.fromisoformat(last_scan_at_iso)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(hours=frequency_hours) - DUE_SLACK


def compute_next_scan_at(
    daily_notify_time: str,
    frequency_hours: int,
    now: datetime,
) -> datetime:
    """Compute the earliest future scan time for modes B/C.
    
    The final scan of the day fires ``_SCAN_LEAD_MINUTES`` before
    ``daily_notify_time``.  Earlier scans are spaced ``frequency_hours``
    apart, walking backwards from that target.

    If the computed time is already past, advances to tomorrow's window.

    Args:
        daily_notify_time: ``HH:MM`` string.
        frequency_hours: Hours between scans.
        now: Timezone-aware reference timestamp.

    Returns:
        The earliest future scan timestamp (timezone-aware UTC).
    """
    notify_t = parse_hhmm(daily_notify_time)
    target_dt = datetime.combine(
        now.date(), notify_t, tzinfo=timezone.utc
    ) - timedelta(minutes=SCAN_LEAD_MINUTES)

    # Walk backwards from the daily target in frequency_hours steps to find
    # the full chain of intermediate scan slots for today.
    slots: list[datetime] = []
    slot = target_dt
    while slot.date() == now.date():
        slots.append(slot)
        slot -= timedelta(hours=frequency_hours)

    # Pick the earliest slot that is still in the future.
    future_slots = [s for s in slots if s > now]
    if future_slots:
        return min(future_slots)

    # All today's slots are in the past — advance the target to tomorrow.
    target_dt += timedelta(days=1)
    slots = []
    slot = target_dt
    tomorrow = target_dt.date()
    while slot.date() == tomorrow:
        slots.append(slot)
        slot -= timedelta(hours=frequency_hours)
    future_slots = [s for s in slots if s > now]
    return min(future_slots) if future_slots else target_dt
