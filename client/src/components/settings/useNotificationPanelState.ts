/**
 * Custom hook encapsulating all state management, persistence, and conflict
 * detection logic for the NotificationSettingsPanel component.
 */

import { useEffect, useState } from "react";
import { en } from "@/i18n/en";
import {
  useNotificationSettings,
  useUpdateNotificationSettings,
  NotificationSettings,
} from "@/api/settingsApi";
import { isTimeInWindow, timeToMinutes } from "./dndTimeUtils";

const s = en.pages.settings.notificationsPanel;

/** Default value for Daily Digest Time when in Mode B or C. */
export const DEFAULT_DAILY_TIME = "18:00";
/** Default value for Immediate Threshold when in Mode C. */
export const DEFAULT_THRESHOLD = 5;
/** Maximum allowed value for Immediate Threshold. */
export const MAX_THRESHOLD = 20;

type ToastState = { message: string; kind: "success" | "error"; duration?: number } | null;

export interface NotificationPanelState {
  settings: NotificationSettings | undefined;
  isLoading: boolean;
  isError: boolean;
  isPending: boolean;
  toast: ToastState;
  setToast: (t: ToastState) => void;
  mode: NotificationSettings["notification_mode"];
  dailyTime: string;
  setDailyTime: (v: string) => void;
  notifyIfZero: boolean;
  setNotifyIfZero: (v: boolean) => void;
  dndStart: string;
  setDndStart: (v: string) => void;
  dndEnd: string;
  setDndEnd: (v: string) => void;
  threshold: number;
  setThreshold: (v: number) => void;
  dndConflict: boolean;
  save: (partial: Partial<NotificationSettings>) => void;
  handleModeChange: (val: NotificationSettings["notification_mode"]) => void;
  attemptConflictResolution: (
    nextDigest: string,
    nextStart: string,
    nextEnd: string,
    extraPartial?: Partial<NotificationSettings>,
  ) => void;
}

/**
 * Hook managing all notification settings state: local drafts, server
 * persistence via mutation, conflict detection when switching to Mode B/C
 * with a DND window overlapping the Daily Digest Time, and automatic
 * rollback on save failure.
 *
 * @returns The full panel state object consumed by NotificationSettingsPanel.
 */
export function useNotificationPanelState(): NotificationPanelState {
  const { data: settings, isLoading, isError } = useNotificationSettings();
  const { mutate: update, isPending } = useUpdateNotificationSettings();

  const [toast, setToast] = useState<ToastState>(null);

  // Local drafts — never empty for required fields in modes B & C
  const [mode, setMode] = useState<NotificationSettings["notification_mode"]>("A");
  const [dailyTime, setDailyTime] = useState<string>(DEFAULT_DAILY_TIME);
  const [notifyIfZero, setNotifyIfZero] = useState<boolean>(false);
  const [dndStart, setDndStart] = useState<string>("");
  const [dndEnd, setDndEnd] = useState<string>("");
  const [threshold, setThreshold] = useState<number>(DEFAULT_THRESHOLD);

  // True when the user switched to B/C but the DND window conflicts with Daily Digest Time.
  // In this state the mode change is NOT persisted; the server remains on the last saved mode.
  const [dndConflict, setDndConflict] = useState<boolean>(false);

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
        const isConflictErr = err.message?.toLowerCase().includes("do not disturb");
        const message = isConflictErr ? s.dndConflictError : (err.message || s.saveError);
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
   * Check if the Daily Digest Time falls inside the DND window.
   *
   * @param digest - Daily digest time (HH:MM).
   * @param start - DND start time (HH:MM).
   * @param end - DND end time (HH:MM).
   * @returns True if the digest time collides with the DND window.
   */
  function hasDndConflict(digest: string, start: string, end: string): boolean {
    if (!digest || !start || !end) return false;
    return isTimeInWindow(timeToMinutes(digest), timeToMinutes(start), timeToMinutes(end));
  }

  /**
   * Handle mode selection changes. Enforces non-empty default values for B and C modes.
   * When switching to B/C with a DND conflict, the save is deferred until the user resolves it.
   *
   * @param val - The new notification mode selected by the user.
   */
  function handleModeChange(val: NotificationSettings["notification_mode"]): void {
    setMode(val);

    // Switching back to A always clears any pending conflict without saving.
    if (val === "A") {
      if (dndConflict) {
        setDndConflict(false);
        setToast(null);
      }
      save({
        notification_mode: val,
        dnd_start: dndStart || null,
        dnd_end: dndEnd || null,
      });
      return;
    }

    // Mode B or C — prepare the update payload.
    const updates: Partial<NotificationSettings> = { notification_mode: val };
    const ensuredTime = dailyTime || DEFAULT_DAILY_TIME;
    setDailyTime(ensuredTime);
    updates.daily_notify_time = ensuredTime;

    if (val === "C") {
      const ensuredThreshold = threshold || DEFAULT_THRESHOLD;
      setThreshold(ensuredThreshold);
      updates.immediate_job_threshold = ensuredThreshold;
    }

    // Check for DND conflict before persisting.
    if (hasDndConflict(ensuredTime, dndStart, dndEnd)) {
      setDndConflict(true);
      setToast({ message: s.dndModeSwitchConflict, kind: "error", duration: 0 });
      return;
    }

    setDndConflict(false);
    save(updates);
  }

  /**
   * Called after a user edits the Daily Digest Time or DND fields while in a
   * pending conflict state. Re-checks the conflict and persists the full mode
   * switch if the conflict has been resolved.
   *
   * @param nextDigest - Current daily digest time value.
   * @param nextStart - Current DND start value.
   * @param nextEnd - Current DND end value.
   * @param extraPartial - Any additional fields to include in the save payload.
   */
  function attemptConflictResolution(
    nextDigest: string,
    nextStart: string,
    nextEnd: string,
    extraPartial?: Partial<NotificationSettings>,
  ): void {
    if (hasDndConflict(nextDigest, nextStart, nextEnd)) return;

    // Conflict resolved — persist the full pending mode switch.
    setDndConflict(false);
    setToast(null);
    const payload: Partial<NotificationSettings> = {
      notification_mode: mode,
      daily_notify_time: nextDigest,
      dnd_start: nextStart || null,
      dnd_end: nextEnd || null,
      ...extraPartial,
    };
    if (mode === "C") {
      payload.immediate_job_threshold = threshold || DEFAULT_THRESHOLD;
    }
    save(payload);
  }

  return {
    settings,
    isLoading,
    isError,
    isPending,
    toast,
    setToast,
    mode,
    dailyTime,
    setDailyTime,
    notifyIfZero,
    setNotifyIfZero,
    dndStart,
    setDndStart,
    dndEnd,
    setDndEnd,
    threshold,
    setThreshold,
    dndConflict,
    save,
    handleModeChange,
    attemptConflictResolution,
  };
}
