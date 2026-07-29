import { useEffect, useState } from "react";
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
import { DndFields } from "./DndFields";
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

        <DndFields
          dndStart={dndStart}
          dndEnd={dndEnd}
          dailyTime={dailyTime}
          isPending={isPending}
          onSave={save}
          onDndStartChange={setDndStart}
          onDndEndChange={setDndEnd}
        />
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
