/**
 * Pure time-arithmetic helpers for the Do-Not-Disturb window in NotificationSettingsPanel.
 */

/**
 * Convert an "HH:MM" string to total minutes from midnight (0-1439).
 *
 * @param timeStr - Time string in "HH:MM" format.
 * @returns Total minutes from midnight, or NaN if invalid.
 */
export function timeToMinutes(timeStr: string): number {
  const parts = timeStr.split(":");
  if (parts.length !== 2) return NaN;
  const h = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  return h * 60 + m;
}

/**
 * Convert total minutes from midnight back to an "HH:MM" formatted string.
 *
 * @param totalMinutes - Total minutes (can be negative or above 1440, will wrap).
 * @returns Formatted "HH:MM" time string.
 */
export function minutesToTime(totalMinutes: number): string {
  const m = ((totalMinutes % 1440) + 1440) % 1440;
  const h = Math.floor(m / 60);
  const mins = m % 60;
  return `${String(h).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}

/**
 * Check if a specific target time falls inside a DND interval [start, end).
 * Handles both same-day intervals and intervals that wrap around midnight.
 *
 * @param targetMin - Target time in minutes from midnight.
 * @param startMin - DND window start in minutes from midnight.
 * @param endMin - DND window end in minutes from midnight.
 * @returns True if target is within the DND window.
 */
export function isTimeInWindow(targetMin: number, startMin: number, endMin: number): boolean {
  if (Number.isNaN(targetMin) || Number.isNaN(startMin) || Number.isNaN(endMin)) return false;
  if (startMin <= endMin) {
    return startMin <= targetMin && targetMin < endMin;
  }
  return targetMin >= startMin || targetMin < endMin;
}

/**
 * Calculate the automatic DND End time given a Start time and the Daily Digest time.
 * Defaults to start + 8 hours, but if the window collides with Daily Digest time,
 * caps the end time to 30 minutes before Daily Digest time.
 *
 * @param startStr - The "HH:MM" start time.
 * @param dailyNotifyStr - The "HH:MM" daily digest time.
 * @returns The collision-safe "HH:MM" end time.
 */
export function calculateAutoDndEnd(startStr: string, dailyNotifyStr: string): string {
  const startMin = timeToMinutes(startStr);
  if (Number.isNaN(startMin)) return "";
  
  const defaultEndMin = (startMin + 8 * 60) % 1440;
  const notifyMin = timeToMinutes(dailyNotifyStr);

  if (!Number.isNaN(notifyMin) && isTimeInWindow(notifyMin, startMin, defaultEndMin)) {
    return minutesToTime(notifyMin - 30);
  }
  return minutesToTime(defaultEndMin);
}

/**
 * Calculate the automatic DND Start time given an End time and the Daily Digest time.
 * Defaults to end - 8 hours, but if the window collides with Daily Digest time,
 * floors the start time to 30 minutes after Daily Digest time.
 *
 * @param endStr - The "HH:MM" end time.
 * @param dailyNotifyStr - The "HH:MM" daily digest time.
 * @returns The collision-safe "HH:MM" start time.
 */
export function calculateAutoDndStart(endStr: string, dailyNotifyStr: string): string {
  const endMin = timeToMinutes(endStr);
  if (Number.isNaN(endMin)) return "";

  const defaultStartMin = (((endMin - 8 * 60) % 1440) + 1440) % 1440;
  const notifyMin = timeToMinutes(dailyNotifyStr);

  if (!Number.isNaN(notifyMin) && isTimeInWindow(notifyMin, defaultStartMin, endMin)) {
    return minutesToTime(notifyMin + 30);
  }
  return minutesToTime(defaultStartMin);
}
