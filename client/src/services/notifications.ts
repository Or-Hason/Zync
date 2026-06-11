/**
 * Cross-platform notification dispatcher.
 *
 * Wraps the Tauri plugin-notification API (desktop) and the browser
 * Notifications API (web) behind a single `fireNotification` call.
 * Navigation on click is decoupled via a custom window event so this module
 * does not need a React Router reference.
 */

import { en } from "@/i18n/en";

const s = en.notifications;

/** Fires a `zync:navigate-job` window event that the useNotifications hook handles. */
function dispatchNavigateJob(jobId: string): void {
  window.dispatchEvent(
    new CustomEvent<{ jobId: string }>("zync:navigate-job", { detail: { jobId } }),
  );
}

// ── Tauri ─────────────────────────────────────────────────────────────────

const TAURI_ACTION_TYPE = "job_match";
let _tauriReady = false;

/**
 * One-time Tauri notification setup: registers the action type and installs
 * the click → navigate handler. Idempotent — safe to call on every mount.
 */
export async function setupTauriNotifications(): Promise<void> {
  if (_tauriReady) return;
  _tauriReady = true;

  const { registerActionTypes, onAction } =
    await import("@tauri-apps/plugin-notification");

  await registerActionTypes([
    { id: TAURI_ACTION_TYPE, actions: [{ id: "view", title: "View Job", foreground: true }] },
  ]);

  await onAction((notification) => {
    const jobId = (notification.extra as { jobId?: string } | undefined)?.jobId;
    if (jobId) dispatchNavigateJob(jobId);
  });
}

async function fireTauriNotification(
  title: string,
  body: string,
  jobId: string,
): Promise<void> {
  const { isPermissionGranted, requestPermission, sendNotification } =
    await import("@tauri-apps/plugin-notification");

  if (!(await isPermissionGranted())) {
    const perm = await requestPermission();
    if (perm !== "granted") return;
  }

  sendNotification({ title, body, actionTypeId: TAURI_ACTION_TYPE, extra: { jobId } });
}

// ── Web Notifications API ────────────────────────────────────────────────

async function fireWebNotification(
  title: string,
  body: string,
  jobId: string,
): Promise<void> {
  if (!("Notification" in window) || Notification.permission === "denied") return;

  if (Notification.permission !== "granted") {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return;
  }

  const notif = new Notification(title, { body });
  notif.onclick = (): void => {
    window.focus();
    dispatchNavigateJob(jobId);
  };
}

// ── Public API ───────────────────────────────────────────────────────────

/**
 * Fire a job-match notification using the correct platform API.
 *
 * @param jobTitle - Job title shown in the notification body.
 * @param matchScore - Match score (0–100).
 * @param jobId - Job UUID for the deep-link target.
 */
export async function fireNotification(
  jobTitle: string,
  matchScore: number,
  jobId: string,
): Promise<void> {
  const title = s.title;
  const body = s.body.replace("{jobTitle}", jobTitle).replace("{score}", String(matchScore));

  if ("__TAURI__" in window) {
    await fireTauriNotification(title, body, jobId);
  } else {
    await fireWebNotification(title, body, jobId);
  }
}
