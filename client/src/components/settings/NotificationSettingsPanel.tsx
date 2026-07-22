import { useEffect, useState } from "react";
import { en } from "@/i18n/en";
import {
  useNotificationSettings,
  useUpdateNotificationSettings,
  NotificationSettings,
} from "@/api/settingsApi";
import { Toast } from "@/components/resume/Toast";
import styles from "./AutoScanPanel.module.css";

const s = en.pages.settings.notificationsPanel;

type ToastState = { message: string; kind: "success" | "error" } | null;

/**
 * Settings panel controlling notification preferences:
 * mode (A, B, C), daily digest time, DND window, and threshold.
 */
export function NotificationSettingsPanel(): React.JSX.Element {
  const { data: settings, isLoading, isError } = useNotificationSettings();
  const { mutate: update, isPending } = useUpdateNotificationSettings();

  const [toast, setToast] = useState<ToastState>(null);
  
  // Local drafts
  const [mode, setMode] = useState<NotificationSettings["notification_mode"]>("A");
  const [dailyTime, setDailyTime] = useState<string>("");
  const [notifyIfZero, setNotifyIfZero] = useState<boolean>(false);
  const [dndStart, setDndStart] = useState<string>("");
  const [dndEnd, setDndEnd] = useState<string>("");
  const [threshold, setThreshold] = useState<string>("");

  useEffect(() => {
    if (settings) {
      setMode(settings.notification_mode);
      setDailyTime(settings.daily_notify_time || "");
      setNotifyIfZero(settings.notify_if_zero);
      setDndStart(settings.dnd_start || "");
      setDndEnd(settings.dnd_end || "");
      setThreshold(settings.immediate_job_threshold ? String(settings.immediate_job_threshold) : "");
    }
  }, [settings]);

  function save(partial: Partial<NotificationSettings>): void {
    if (!settings) return;
    const next: NotificationSettings = { ...settings, ...partial };
    
    // Normalize empty strings to null for backend schema
    if (next.daily_notify_time === "") next.daily_notify_time = null;
    if (next.dnd_start === "") next.dnd_start = null;
    if (next.dnd_end === "") next.dnd_end = null;

    update(next, {
      onSuccess: () => setToast({ message: s.savedToast, kind: "success" }),
      onError: (err: Error & { status?: number }) => {
        const message = err.message || s.saveError;
        setToast({ message, kind: "error" });
        // Rollback local drafts on error
        if (settings) {
          setMode(settings.notification_mode);
          setDailyTime(settings.daily_notify_time || "");
          setNotifyIfZero(settings.notify_if_zero);
          setDndStart(settings.dnd_start || "");
          setDndEnd(settings.dnd_end || "");
          setThreshold(settings.immediate_job_threshold ? String(settings.immediate_job_threshold) : "");
        }
      },
    });
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
        <div className={styles.row}>
          <label htmlFor="notif-mode" className={styles.label}>
            {s.modeLabel}
          </label>
          <select
            id="notif-mode"
            className={styles.select}
            value={mode}
            disabled={isPending}
            onChange={(e) => {
              const val = e.target.value as NotificationSettings["notification_mode"];
              setMode(val);
              save({ notification_mode: val });
            }}
          >
            <option value="A">{s.modeA}</option>
            <option value="B">{s.modeB}</option>
            <option value="C">{s.modeC}</option>
          </select>
        </div>

        {(mode === "B" || mode === "C") && (
          <div className={styles.row}>
            <label htmlFor="daily-time" className={styles.label}>
              {s.dailyTimeLabel}
              <span className={styles.hint}>{s.dailyTimeHint}</span>
            </label>
            <input
              id="daily-time"
              className={styles.input}
              type="time"
              value={dailyTime}
              disabled={isPending}
              onChange={(e) => setDailyTime(e.target.value)}
              onBlur={() => save({ daily_notify_time: dailyTime || null })}
            />
          </div>
        )}

        {(mode === "B" || mode === "C") && (
          <div className={styles.row}>
            <label className={styles.checkboxLabel}>
              <input
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
              {s.notifyIfZeroLabel}
            </label>
          </div>
        )}

        {mode === "C" && (
          <div className={styles.row}>
            <label htmlFor="threshold" className={styles.label}>
              {s.thresholdLabel}
              <span className={styles.hint}>{s.thresholdHint}</span>
            </label>
            <input
              id="threshold"
              className={styles.input}
              type="number"
              min="1"
              value={threshold}
              disabled={isPending}
              onChange={(e) => setThreshold(e.target.value)}
              onBlur={() => {
                const val = parseInt(threshold, 10);
                const final = Number.isNaN(val) || val < 1 ? null : val;
                save({ immediate_job_threshold: final });
              }}
            />
          </div>
        )}

        <div className={styles.row}>
          <label className={styles.label}>{s.dndLabel}</label>
          <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="dnd-start">{s.dndStartLabel}</label>
              <input
                id="dnd-start"
                className={styles.input}
                type="time"
                value={dndStart}
                disabled={isPending}
                onChange={(e) => setDndStart(e.target.value)}
                onBlur={() => save({ dnd_start: dndStart || null })}
              />
            </div>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="dnd-end">{s.dndEndLabel}</label>
              <input
                id="dnd-end"
                className={styles.input}
                type="time"
                value={dndEnd}
                disabled={isPending}
                onChange={(e) => setDndEnd(e.target.value)}
                onBlur={() => save({ dnd_end: dndEnd || null })}
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
