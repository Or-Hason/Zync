import { useEffect, useRef, useState } from "react";
import { en } from "@/i18n/en";
import {
  useNotificationSettings,
  useUpdateNotificationSettings,
  NotificationSettings,
} from "@/api/settingsApi";
import {
  isInAppSoundEnabled,
  playInAppNotificationSound,
  setInAppSoundEnabled,
} from "@/services/notifications";
import { Toast } from "@/components/resume/Toast";
import styles from "./NotificationSettingsPanel.module.css";

const s = en.pages.settings.notificationsPanel;

/** Default value for Daily Digest Time when in Mode B or C. */
const DEFAULT_DAILY_TIME = "18:00";
/** Default value for Immediate Threshold when in Mode C. */
const DEFAULT_THRESHOLD = 5;
/** Maximum allowed value for Immediate Threshold. */
const MAX_THRESHOLD = 20;

type ToastState = { message: string; kind: "success" | "error" } | null;

/**
 * Convert an "HH:MM" string to total minutes from midnight (0-1439).
 *
 * @param timeStr - Time string in "HH:MM" format.
 * @returns Total minutes from midnight, or NaN if invalid.
 */
function timeToMinutes(timeStr: string): number {
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
function minutesToTime(totalMinutes: number): string {
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
function isTimeInWindow(targetMin: number, startMin: number, endMin: number): boolean {
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
function calculateAutoDndEnd(startStr: string, dailyNotifyStr: string): string {
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
function calculateAutoDndStart(endStr: string, dailyNotifyStr: string): string {
  const endMin = timeToMinutes(endStr);
  if (Number.isNaN(endMin)) return "";

  const defaultStartMin = (((endMin - 8 * 60) % 1440) + 1440) % 1440;
  const notifyMin = timeToMinutes(dailyNotifyStr);

  if (!Number.isNaN(notifyMin) && isTimeInWindow(notifyMin, defaultStartMin, endMin)) {
    return minutesToTime(notifyMin + 30);
  }
  return minutesToTime(defaultStartMin);
}

/**
 * Settings panel controlling notification preferences:
 * mode (A, B, C), daily digest time, automatic DND pairing (+/- 8h), immediate threshold (max 20), and in-app sound alert.
 *
 * @returns The rendered notification preferences panel.
 */
export function NotificationSettingsPanel(): React.JSX.Element {
  const { data: settings, isLoading, isError } = useNotificationSettings();
  const { mutate: update, isPending } = useUpdateNotificationSettings();

  const [toast, setToast] = useState<ToastState>(null);
  const [inAppSound, setInAppSound] = useState<boolean>(isInAppSoundEnabled());

  // Local drafts — never empty for required fields in modes B & C
  const [mode, setMode] = useState<NotificationSettings["notification_mode"]>("A");
  const [dailyTime, setDailyTime] = useState<string>(DEFAULT_DAILY_TIME);
  const [notifyIfZero, setNotifyIfZero] = useState<boolean>(false);
  const [dndStart, setDndStart] = useState<string>("");
  const [dndEnd, setDndEnd] = useState<string>("");

  const dndStartRef = useRef<HTMLInputElement>(null);
  const dndEndRef = useRef<HTMLInputElement>(null);
  const [threshold, setThreshold] = useState<number>(DEFAULT_THRESHOLD);

  useEffect(() => {
    if (settings) {
      setMode(settings.notification_mode);
      setDailyTime(settings.daily_notify_time ?? DEFAULT_DAILY_TIME);
      setNotifyIfZero(settings.notify_if_zero);
      setDndStart(settings.dnd_start ?? "");
      setDndEnd(settings.dnd_end ?? "");
      setThreshold(settings.immediate_job_threshold ?? DEFAULT_THRESHOLD);
    }
  }, [settings]);

  function save(partial: Partial<NotificationSettings>): void {
    if (!settings) return;
    const next: NotificationSettings = { ...settings, ...partial };

    update(next, {
      onSuccess: () => setToast({ message: s.savedToast, kind: "success" }),
      onError: (err: Error & { status?: number }) => {
        const isConflict = err.message?.toLowerCase().includes("do not disturb");
        const message = isConflict ? s.dndConflictError : (err.message || s.saveError);
        setToast({ message, kind: "error" });
        // Rollback local drafts to last persisted values on error
        if (settings) {
          setMode(settings.notification_mode);
          setDailyTime(settings.daily_notify_time ?? DEFAULT_DAILY_TIME);
          setNotifyIfZero(settings.notify_if_zero);
          setDndStart(settings.dnd_start ?? "");
          setDndEnd(settings.dnd_end ?? "");
          setThreshold(settings.immediate_job_threshold ?? DEFAULT_THRESHOLD);
        }
      },
    });
  }

  /**
   * Handle mode selection changes. Enforces non-empty default values for B and C modes.
   *
   * @param val - The new notification mode selected by the user.
   */
  function handleModeChange(val: NotificationSettings["notification_mode"]): void {
    setMode(val);
    const updates: Partial<NotificationSettings> = { notification_mode: val };
    if (val === "B" || val === "C") {
      const ensuredTime = dailyTime || DEFAULT_DAILY_TIME;
      setDailyTime(ensuredTime);
      updates.daily_notify_time = ensuredTime;
    }
    if (val === "C") {
      const ensuredThreshold = threshold || DEFAULT_THRESHOLD;
      setThreshold(ensuredThreshold);
      updates.immediate_job_threshold = ensuredThreshold;
    }
    save(updates);
  }

  /**
   * Force clear partial DOM time input buffer and state when deleting a DND window.
   */
  function clearDndInputs(): void {
    setDndStart("");
    setDndEnd("");
    if (dndStartRef.current) dndStartRef.current.value = "";
    if (dndEndRef.current) dndEndRef.current.value = "";
    save({ dnd_start: null, dnd_end: null });
  }

  /**
   * Handle blur events on the DND Start input. Enforces +/-8h pairing or dual deletion.
   */
  function handleDndStartBlur(): void {
    // Rule: If deleted or incomplete (e.g. 06:--), clear both UI buffer and server state
    if (!dndStart) {
      clearDndInputs();
      return;
    }
    // Rule: If user entered Start time and End is empty, automatically add End time (avoiding Daily Digest collision)
    if (dndStart && !dndEnd) {
      const notifyTime = dailyTime || DEFAULT_DAILY_TIME;
      const calcEnd = calculateAutoDndEnd(dndStart, notifyTime);
      setDndEnd(calcEnd);
      if (dndEndRef.current) dndEndRef.current.value = calcEnd;
      save({ dnd_start: dndStart, dnd_end: calcEnd });
      return;
    }
    // Both values present
    save({ dnd_start: dndStart, dnd_end: dndEnd });
  }

  /**
   * Handle blur events on the DND End input. Enforces +/-8h pairing or dual deletion.
   */
  function handleDndEndBlur(): void {
    // Rule: If deleted or incomplete (e.g. --:30), clear both UI buffer and server state
    if (!dndEnd) {
      clearDndInputs();
      return;
    }
    // Rule: If user entered End time without Start time, automatically set Start time (avoiding Daily Digest collision)
    if (dndEnd && !dndStart) {
      const notifyTime = dailyTime || DEFAULT_DAILY_TIME;
      const calcStart = calculateAutoDndStart(dndEnd, notifyTime);
      setDndStart(calcStart);
      if (dndStartRef.current) dndStartRef.current.value = calcStart;
      save({ dnd_start: calcStart, dnd_end: dndEnd });
      return;
    }
    // Both values present
    save({ dnd_start: dndStart, dnd_end: dndEnd });
  }

  if (isLoading) {
    return (
      <section className={styles.panel}>
        <p className={styles.loading}>{s.loading}</p>
      </section>
    );
  }

  if (isError || !settings) {
    return (
      <section className={styles.panel}>
        <p className={styles.error}>{s.fetchError}</p>
      </section>
    );
  }

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>{s.title}</h2>
        <p className={styles.subtitle}>{s.subtitle}</p>
      </div>

      <div className={styles.content}>
        {/* Notification Mode */}
        <div className={styles.field}>
          <label htmlFor="notif-mode" className={styles.label}>
            {s.modeLabel}
          </label>
          <select
            id="notif-mode"
            className={styles.select}
            value={mode}
            disabled={isPending}
            onChange={(e) => handleModeChange(e.target.value as NotificationSettings["notification_mode"])}
          >
            <option value="A">{s.modeA}</option>
            <option value="B">{s.modeB}</option>
            <option value="C">{s.modeC}</option>
          </select>
        </div>

        {/* In-app sound toggle — always visible */}
        <div className={styles.checkboxRow}>
          <input
            id="in-app-sound"
            type="checkbox"
            className={styles.checkbox}
            checked={inAppSound}
            onChange={(e) => {
              const val = e.target.checked;
              setInAppSound(val);
              setInAppSoundEnabled(val);
              if (val) {
                playInAppNotificationSound();
              }
            }}
          />
          <label htmlFor="in-app-sound" className={styles.checkboxLabel}>
            {s.soundLabel}
          </label>
        </div>

        {/* Daily Digest Time — modes B & C only */}
        {(mode === "B" || mode === "C") && (
          <div className={styles.field}>
            <label htmlFor="daily-time" className={styles.label}>
              {s.dailyTimeLabel}
            </label>
            <input
              id="daily-time"
              className={styles.input}
              type="time"
              value={dailyTime}
              disabled={isPending}
              onChange={(e) => {
                if (e.target.value) setDailyTime(e.target.value);
              }}
              onBlur={() => {
                const val = dailyTime || DEFAULT_DAILY_TIME;
                if (!dailyTime) setDailyTime(val);
                save({ daily_notify_time: val });
              }}
            />
            <span className={styles.hint}>{s.dailyTimeHint}</span>
          </div>
        )}

        {/* Notify if zero — modes B & C only */}
        {(mode === "B" || mode === "C") && (
          <div className={styles.checkboxRow}>
            <input
              id="notify-if-zero"
              type="checkbox"
              className={styles.checkbox}
              checked={notifyIfZero}
              disabled={isPending}
              onChange={(e) => {
                const val = e.target.checked;
                setNotifyIfZero(val);
                save({ notify_if_zero: val });
              }}
            />
            <label htmlFor="notify-if-zero" className={styles.checkboxLabel}>
              {s.notifyIfZeroLabel}
            </label>
          </div>
        )}

        {/* Immediate Threshold — mode C only */}
        {mode === "C" && (
          <div className={styles.field}>
            <label htmlFor="threshold" className={styles.label}>
              {s.thresholdLabel}
            </label>
            <input
              id="threshold"
              className={styles.input}
              type="number"
              min="1"
              max={String(MAX_THRESHOLD)}
              value={threshold}
              disabled={isPending}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!Number.isNaN(val)) setThreshold(val);
              }}
              onBlur={() => {
                const final = Math.min(
                  MAX_THRESHOLD,
                  Math.max(1, Number.isNaN(threshold) ? DEFAULT_THRESHOLD : threshold)
                );
                setThreshold(final);
                save({ immediate_job_threshold: final });
              }}
            />
            <span className={styles.hint}>{s.thresholdHint}</span>
          </div>
        )}

        {/* Do Not Disturb */}
        <div className={styles.dndRow}>
          <label className={styles.label}>{s.dndLabel}</label>
          <div className={styles.dndInputs}>
            <div className={styles.dndGroup}>
              <label htmlFor="dnd-start" className={styles.dndGroupLabel}>
                {s.dndStartLabel}
              </label>
              <input
                id="dnd-start"
                ref={dndStartRef}
                className={styles.input}
                type="time"
                value={dndStart}
                disabled={isPending}
                onChange={(e) => setDndStart(e.target.value)}
                onBlur={handleDndStartBlur}
              />
            </div>
            <div className={styles.dndGroup}>
              <label htmlFor="dnd-end" className={styles.dndGroupLabel}>
                {s.dndEndLabel}
              </label>
              <input
                id="dnd-end"
                ref={dndEndRef}
                className={styles.input}
                type="time"
                value={dndEnd}
                disabled={isPending}
                onChange={(e) => setDndEnd(e.target.value)}
                onBlur={handleDndEndBlur}
              />
            </div>
          </div>
        </div>
      </div>

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={() => setToast(null)}
        />
      )}
    </section>
  );
}
