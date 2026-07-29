import { useEffect, useState } from "react";
import { en } from "@/i18n/en";
import {
  SCAN_FREQUENCY_CHOICES,
  useScanStatusPolling,
  useUpdateScanSettings,
} from "@/api/settingsApi";
import type { ScanFrequencyHours, ScanSettings } from "@/api/settingsApi";
import { useActiveResume } from "@/api/resumeApi";
import { DISMISSED_KEY } from "@/components/NotificationCTA";
import { Toast } from "@/components/resume/Toast";
import { dispatchTestNotification } from "@/hooks/useNotifications";
import styles from "./AutoScanPanel.module.css";

const s = en.pages.settings.autoScan;

const THRESHOLD_MIN = 0;
const THRESHOLD_MAX = 100;

/** Format milliseconds remaining as HH:MM:SS. */
function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

type ToastState = { message: string; kind: "success" | "error" } | null;

/** Clamp a score threshold into the inclusive 0–100 range. */
function clampThreshold(value: number): number {
  if (Number.isNaN(value)) return THRESHOLD_MIN;
  return Math.min(THRESHOLD_MAX, Math.max(THRESHOLD_MIN, Math.round(value)));
}

/** Human-readable "Every N hour(s)" label for a frequency choice. */
function frequencyLabel(hours: number): string {
  const suffix = hours === 1 ? s.frequencyHourSuffix : s.frequencyHoursSuffix;
  return `${s.frequencyEveryPrefix} ${hours} ${suffix}`;
}

/**
 * Settings panel controlling background auto-scanning: master toggle, scan
 * frequency, and the notification score threshold. The toggle is disabled with
 * an explanatory hint when no active resume exists, mirroring the backend
 * invariant that auto-scan cannot run without one.
 *
 * @returns The rendered auto-scan settings panel.
 */
export function AutoScanPanel(): React.JSX.Element {
  const { data: settings, isLoading, isError } = useScanStatusPolling();
  const { mutate: update, isPending } = useUpdateScanSettings();
  const { data: activeResume } = useActiveResume();

  const [toast, setToast] = useState<ToastState>(null);
  const [thresholdDraft, setThresholdDraft] = useState<string>("");
  const [countdown, setCountdown] = useState<number | null>(null);
  const [testCountdown, setTestCountdown] = useState<number | null>(null);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | null>(
    typeof window !== "undefined" && "Notification" in window ? Notification.permission : null,
  );
  const [ctaDismissed] = useState(() => localStorage.getItem(DISMISSED_KEY) === "true");

  // Keep the threshold input synced with the server value when it loads/changes.
  useEffect(() => {
    if (settings) setThresholdDraft(String(settings.notification_score_threshold));
  }, [settings]);

  // Local countdown clock — ticks every second; anchored to server last_scan_at.
  useEffect(() => {
    if (!settings?.auto_scan_enabled || !settings.last_scan_at) {
      setCountdown(null);
      return;
    }
    // Normalize Python microsecond timestamps ("…123456+00:00") to milliseconds so
    // Date.parse never returns NaN on stricter JS engines.
    const normalized = settings.last_scan_at.replace(/(\.\d{3})\d+/, "$1");
    const nextAt = new Date(normalized).getTime() + settings.scan_frequency_hours * 3_600_000;
    if (Number.isNaN(nextAt)) {
      setCountdown(null);
      return;
    }
    const tick = (): void => setCountdown(Math.max(0, nextAt - Date.now()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [settings?.auto_scan_enabled, settings?.last_scan_at, settings?.scan_frequency_hours]);

  const hasActiveResume = Boolean(activeResume);

  function save(partial: Partial<ScanSettings>): void {
    if (!settings) return;
    const next: ScanSettings = { ...settings, ...partial };
    update(next, {
      onSuccess: () => setToast({ message: s.savedToast, kind: "success" }),
      onError: (err: Error & { status?: number }) => {
        // Reset the draft so the input never drifts from the persisted value.
        setThresholdDraft(String(settings.notification_score_threshold));
        const message = err.status === 400 ? s.enableConflict : s.saveError;
        setToast({ message, kind: "error" });
      },
    });
  }

  function handleToggle(enabled: boolean): void {
    if (enabled && !("__TAURI__" in window) && notifPermission === "default") {
      void Notification.requestPermission().then(setNotifPermission);
    }
    save({ auto_scan_enabled: enabled });
  }

  function handleFrequency(hours: ScanFrequencyHours): void {
    save({ scan_frequency_hours: hours });
  }

  function commitThreshold(): void {
    if (!settings) return;
    const clamped = clampThreshold(Number(thresholdDraft));
    setThresholdDraft(String(clamped));
    if (clamped !== settings.notification_score_threshold) {
      save({ notification_score_threshold: clamped });
    }
  }

  function handleThresholdKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") e.currentTarget.blur();
  }

  function handleTestTrigger(jobCount: number): void {
    if (testCountdown !== null) return;
    let remaining = 3;
    setTestCountdown(remaining);
    const timer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(timer);
        setTestCountdown(null);
        dispatchTestNotification({
          job_id: "mock-test-job-id",
          job_title: "Senior Full-Stack AI Automation Engineer",
          match_score: 96,
          job_count: jobCount,
          silent: false,
        });
      } else {
        setTestCountdown(remaining);
      }
    }, 1000);
  }

  async function handleBackendMock(): Promise<void> {
    try {
      const res = await fetch("/api/notifications/mock-backend-scan", { method: "POST" });
      if (!res.ok) {
        console.error("[AutoScanPanel] Backend mock failed:", res.status, res.statusText);
      } else {
        console.log("[AutoScanPanel] Backend mock triggered successfully! Waiting for SSE delivery...");
      }
    } catch (err) {
      console.error("[AutoScanPanel] Network error hitting backend mock endpoint:", err);
    }
  }

  const controlsDisabled = isPending || !settings;
  const subControlsDisabled = controlsDisabled || !settings?.auto_scan_enabled;

  return (
    <section className={styles.panel} aria-labelledby="auto-scan-title">
      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={(): void => setToast(null)}
        />
      )}

      <div className={styles.panelHeader}>
        <h2 id="auto-scan-title" className={styles.panelTitle}>{s.title}</h2>
        <p className={styles.panelSubtitle}>{s.subtitle}</p>
      </div>

      {isLoading && (
        <p className={styles.stateText} aria-busy="true">{s.loading}</p>
      )}

      {isError && (
        <p className={styles.errorState} role="alert">{s.fetchError}</p>
      )}

      {!isLoading && !isError && settings && (
        <div className={styles.body}>
          <div className={styles.toggleRow}>
            <label className={styles.toggle}>
              <input
                type="checkbox"
                className={styles.toggleInput}
                checked={settings.auto_scan_enabled}
                disabled={controlsDisabled || !hasActiveResume}
                onChange={(e): void => handleToggle(e.target.checked)}
                aria-label={s.enableAriaLabel}
              />
              <span className={styles.toggleTrack} aria-hidden="true">
                <span className={styles.toggleThumb} />
              </span>
              <span className={styles.toggleLabel}>{s.enableLabel}</span>
            </label>
            {!hasActiveResume && (
              <p className={styles.hint} role="note">{s.noActiveResumeHint}</p>
            )}
            {!("__TAURI__" in window) && notifPermission === "denied" && (
              <p className={styles.notifBlockedHint} role="note">{s.notifBlockedHint}</p>
            )}
            {!("__TAURI__" in window) && notifPermission === "default" && ctaDismissed && settings.auto_scan_enabled && (
              <p className={styles.notifBlockedHint} role="note">{s.notifMutedHint}</p>
            )}
          </div>

          {settings.auto_scan_enabled && (
            <div className={styles.field}>
              <span className={styles.fieldLabel}>{s.nextScanLabel}</span>
              <div className={styles.timerDisplay}>
                {settings.scan_in_progress
                  ? s.scanningNow
                  : settings.last_scan_at
                    ? countdown === null
                      ? "—"
                      : countdown > 0
                        ? formatCountdown(countdown)
                        : s.scanDue
                    : s.pendingFirstScan}
              </div>
            </div>
          )}

          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="scan-frequency">
              {s.frequencyLabel}
            </label>
            <select
              id="scan-frequency"
              className={styles.select}
              value={settings.scan_frequency_hours}
              disabled={subControlsDisabled}
              onChange={(e): void =>
                handleFrequency(Number(e.target.value) as ScanFrequencyHours)
              }
              aria-label={s.frequencyAriaLabel}
            >
              {SCAN_FREQUENCY_CHOICES.map((hours) => (
                <option key={hours} value={hours}>
                  {frequencyLabel(hours)}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="scan-threshold">
              {s.thresholdLabel}
            </label>
            <input
              id="scan-threshold"
              className={styles.numberInput}
              type="number"
              min={THRESHOLD_MIN}
              max={THRESHOLD_MAX}
              step={1}
              value={thresholdDraft}
              disabled={subControlsDisabled}
              onChange={(e): void => setThresholdDraft(e.target.value)}
              onBlur={commitThreshold}
              onKeyDown={handleThresholdKeyDown}
              aria-label={s.thresholdAriaLabel}
            />
            <p className={styles.hint}>{s.thresholdHint}</p>
          </div>

          <div className={styles.field} style={{ marginTop: "1.5rem", borderTop: "1px dashed var(--color-border, rgba(255,255,255,0.15))", paddingTop: "1.25rem" }}>
            <span className={styles.fieldLabel}>Diagnostic Tools (Mock Trigger)</span>
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className={styles.select}
                style={{ cursor: testCountdown !== null ? "not-allowed" : "pointer", padding: "0.5rem 1rem", height: "auto", width: "auto", minWidth: "180px", textAlign: "center" }}
                disabled={testCountdown !== null}
                onClick={(): void => handleTestTrigger(1)}
              >
                {testCountdown !== null ? `Firing in ${testCountdown}s...` : "Test Single Match (3s delay)"}
              </button>
              <button
                type="button"
                className={styles.select}
                style={{ cursor: testCountdown !== null ? "not-allowed" : "pointer", padding: "0.5rem 1rem", height: "auto", width: "auto", minWidth: "180px", textAlign: "center" }}
                disabled={testCountdown !== null}
                onClick={(): void => handleTestTrigger(4)}
              >
                {testCountdown !== null ? `Firing in ${testCountdown}s...` : "Test 4x Matches (3s delay)"}
              </button>
              <button
                type="button"
                className={styles.select}
                style={{ cursor: "pointer", padding: "0.5rem 1rem", height: "auto", width: "auto", minWidth: "180px", textAlign: "center", border: "1px dashed var(--color-primary)" }}
                onClick={(): void => void handleBackendMock()}
              >
                Trigger Backend Mock
              </button>
            </div>
            <p className={styles.hint} style={{ marginTop: "0.5rem" }}>
              Starts a 3-second delay so you can test focus loss, window minimization, or tab switching without executing live backend scans or burning AI tokens. The Backend Mock tests the entire SSE pipeline from Python to UI. Check DevTools console for detailed pipeline logs.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
