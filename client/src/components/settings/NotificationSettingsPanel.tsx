import { useState } from "react";
import { useScanSettings } from "@/api/settingsApi";
import { en } from "@/i18n/en";
import {
  isInAppSoundEnabled,
  playInAppNotificationSound,
  setInAppSoundEnabled,
} from "@/services/notifications";
import { Toast } from "@/components/resume/Toast";
import { DndFields } from "./DndFields";
import { useNotificationPanelState, DEFAULT_DAILY_TIME, DEFAULT_THRESHOLD, MAX_THRESHOLD } from "./useNotificationPanelState";
import styles from "./NotificationSettingsPanel.module.css";

const s = en.pages.settings.notificationsPanel;

/**
 * Settings panel controlling notification preferences:
 * mode (A, B, C), daily digest time, automatic DND pairing (+/- 8h),
 * immediate threshold (max 20), and in-app sound alert.
 *
 * @returns The rendered notification preferences panel.
 */
export function NotificationSettingsPanel(): React.JSX.Element {
  const {
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
  } = useNotificationPanelState();

  const { data: scanSettings } = useScanSettings();
  const [inAppSound, setInAppSound] = useState<boolean>(isInAppSoundEnabled());

  const autoScanOff = scanSettings?.auto_scan_enabled === false;
  const isDisabled = isPending || autoScanOff;

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
        {autoScanOff && (
          <p className={styles.lockedHint}>
            {s.lockedHint}
          </p>
        )}
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
            disabled={isDisabled}
            onChange={(e) => handleModeChange(e.target.value as "A" | "B" | "C")}
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
            disabled={isDisabled}
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
              className={`${styles.input}${dndConflict ? ` ${styles.conflictInput}` : ""}`}
              type="time"
              value={dailyTime}
              disabled={isDisabled}
              onChange={(e) => {
                if (e.target.value) setDailyTime(e.target.value);
              }}
              onBlur={() => {
                const val = dailyTime || DEFAULT_DAILY_TIME;
                if (!dailyTime) setDailyTime(val);
                if (dndConflict) {
                  attemptConflictResolution(val, dndStart, dndEnd);
                } else {
                  save({ daily_notify_time: val });
                }
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
              disabled={isDisabled}
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
              disabled={isDisabled}
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
          dailyTime={mode === "A" ? "" : dailyTime}
          isPending={isDisabled}
          hasConflict={dndConflict}
          onSave={(partial) => {
            if (dndConflict) {
              const nextStart = partial.dnd_start !== undefined ? (partial.dnd_start ?? "") : dndStart;
              const nextEnd = partial.dnd_end !== undefined ? (partial.dnd_end ?? "") : dndEnd;
              attemptConflictResolution(dailyTime, nextStart, nextEnd, partial);
            } else {
              save(partial);
            }
          }}
          onDndStartChange={setDndStart}
          onDndEndChange={setDndEnd}
        />
      </div>

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          duration={toast.duration}
          onDismiss={() => setToast(null)}
        />
      )}
    </section>
  );
}
