/**
 * Cross-platform notification dispatcher.
 *
 * Wraps the Tauri plugin-notification API (desktop) and the browser
 * Notifications API (web) behind a single `fireNotification` call.
 * Clicking a notification focuses the application window.
 */

import { en } from "@/i18n/en";

const s = en.notifications;

// ── Tauri ─────────────────────────────────────────────────────────────────

const TAURI_ACTION_TYPE = "job_match";
let _tauriReady = false;

/**
 * One-time Tauri setup: registers the action type and installs a click
 * handler that brings the app window to the front. Idempotent.
 */
export async function setupTauriNotifications(): Promise<void> {
  if (_tauriReady) return;
  _tauriReady = true;

  const { registerActionTypes, onAction } =
    await import("@tauri-apps/plugin-notification");
  const { getCurrentWindow } = await import("@tauri-apps/api/window");

  await registerActionTypes([{ id: TAURI_ACTION_TYPE, actions: [] }]);

  // onAction fires when the user clicks the notification body or any action.
  // We use it solely to programmatically focus the window.
  await onAction(async () => {
    const win = getCurrentWindow();
    await win.unminimize();
    await win.show();
    await win.setFocus();
  });
}

async function fireTauriNotification(title: string, body: string): Promise<void> {
  const { isPermissionGranted, requestPermission, sendNotification } =
    await import("@tauri-apps/plugin-notification");

  if (!(await isPermissionGranted())) {
    const perm = await requestPermission();
    if (perm !== "granted") return;
  }

  sendNotification({ title, body, actionTypeId: TAURI_ACTION_TYPE });
}

// ── Web Notifications API ────────────────────────────────────────────────

async function fireWebNotification(title: string, body: string): Promise<void> {
  if (!("Notification" in window) || Notification.permission === "denied") return;

  if (Notification.permission !== "granted") {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return;
  }

  const notif = new Notification(title, { body });
  notif.onclick = (e): void => {
    e.preventDefault();
    notif.close();
    window.focus();
  };
}

// ── Public API ───────────────────────────────────────────────────────────

/**
 * Fire a job-match notification using the correct platform API.
 *
 * @param jobTitle - Job title shown in the notification body.
 * @param matchScore - Match score (0–100).
 */
export async function fireNotification(
  jobTitle: string,
  matchScore: number,
): Promise<void> {
  const title = s.title;
  const body = s.body.replace("{jobTitle}", jobTitle).replace("{score}", String(matchScore));

  if ("__TAURI__" in window) {
    await fireTauriNotification(title, body);
  } else {
    await fireWebNotification(title, body);
  }
}
