/**
 * Developer diagnostic tools sub-component extracted from AutoScanPanel.
 */

import { useState } from "react";
import { API_BASE } from "@/api/apiBase";
import { dispatchTestNotification } from "@/hooks/useNotifications";
import styles from "./AutoScanPanel.module.css";

/**
 * Mock notification triggers used to exercise the alert pipeline without
 * running a live scan: two client-side dispatches behind a 3-second delay,
 * plus a backend mock covering the full Python → SSE → UI path. Owns the
 * countdown state locally because nothing outside this block observes it.
 *
 * @returns The rendered diagnostic tools block.
 */
export function ScanDiagnosticsPanel(): React.JSX.Element {
  const [testCountdown, setTestCountdown] = useState<number | null>(null);

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
      const res = await fetch(`${API_BASE}/api/notifications/mock-backend-scan`, { method: "POST" });
      if (!res.ok) {
        console.error("[AutoScanPanel] Backend mock failed:", res.status, res.statusText);
      } else {
        console.log("[AutoScanPanel] Backend mock triggered successfully! Waiting for SSE delivery...");
      }
    } catch (err) {
      console.error("[AutoScanPanel] Network error hitting backend mock endpoint:", err);
    }
  }

  return (
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
  );
}
