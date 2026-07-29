/**
 * Cross-platform notification dispatcher and acoustic chime generator.
 *
 * Wraps the Tauri plugin-notification API (desktop) and the browser
 * Notifications API (web) behind a single `fireNotification` call.
 * Handles click routing strictly through authentic event listeners without ever
 * hijacking window focus or reopening events.
 */

import { en } from "@/i18n/en";

const s = en.notifications;

// ── Audio Alert & Preferences ─────────────────────────────────────────────

const SOUND_PREF_KEY = "zync_in_app_sound_enabled";

interface WebkitWindow extends Window {
  webkitAudioContext?: typeof AudioContext;
}

/**
 * Check whether the in-app audio alert is enabled in user preferences.
 *
 * @returns True if enabled (default), false otherwise.
 */
export function isInAppSoundEnabled(): boolean {
  try {
    return localStorage.getItem(SOUND_PREF_KEY) !== "false";
  } catch {
    return true;
  }
}

/**
 * Update the user preference for in-app notification audio alerts.
 *
 * @param enabled - Whether the alert audio should be played when toasts trigger.
 */
export function setInAppSoundEnabled(enabled: boolean): void {
  try {
    localStorage.setItem(SOUND_PREF_KEY, String(enabled));
  } catch {
    // ignore storage access exceptions
  }
}

/**
 * Synthesizes a subtle, premium two-note chime (C5 → E5) using the browser's
 * Web Audio API. Requires no network download or audio file bundling.
 * Will silently exit if sound is disabled in user preferences or audio is locked.
 */
export function playInAppNotificationSound(): void {
  if (!isInAppSoundEnabled()) return;
  try {
    const AudioContextClass =
      window.AudioContext || (window as unknown as WebkitWindow).webkitAudioContext;
    if (!AudioContextClass) return;

    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    // Gentle ascending chime: C5 (523.25 Hz) immediately, transitioning to E5 (659.25 Hz) after 120ms
    osc.frequency.setValueAtTime(523.25, ctx.currentTime);
    osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.12);

    // Audio volume envelope: peak volume at start, smoothly fading over 400ms
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (err) {
    console.error("[notifications.ts] Failed to synthesize audio chime:", err);
  }
}

// ── Tauri & Global Callbacks ──────────────────────────────────────────────

const TAURI_ACTION_TYPE = "job_match";
let _tauriReady = false;
/** Holds the active navigation callback to execute when an OS notification is explicitly clicked. */
let _activeNotificationCallback: (() => void) | null = null;

/**
 * One-time Tauri setup: registers action types with explicit interactive buttons and installs
 * authentic click handlers (onAction) to execute routing ONLY when clicked. Idempotent.
 */
export async function setupTauriNotifications(): Promise<void> {
  console.log("[notifications.ts] setupTauriNotifications called. _tauriReady =", _tauriReady);
  if (_tauriReady) return;
  _tauriReady = true;

  try {
    const { registerActionTypes, onAction } =
      await import("@tauri-apps/plugin-notification");
    const { getCurrentWindow } = await import("@tauri-apps/api/window");

    console.log("[notifications.ts] Registering Tauri action types:", TAURI_ACTION_TYPE);
    await registerActionTypes([
      {
        id: TAURI_ACTION_TYPE,
        actions: [
          {
            id: "view_match",
            title: s.viewMatches || "View matches",
            foreground: true,
          },
        ],
      },
    ]);
    console.log("[notifications.ts] Tauri action types registered successfully.");

    // Only execute navigation when an explicit notification action or body click is received via IPC
    await onAction(async (notification) => {
      console.log("[notifications.ts] Tauri notification onAction triggered:", notification);
      const win = getCurrentWindow();
      await win.unminimize();
      await win.show();
      await win.setFocus();
      if (_activeNotificationCallback) {
        console.log("[notifications.ts] Executing navigation callback from Tauri onAction");
        const cb = _activeNotificationCallback;
        _activeNotificationCallback = null;
        cb();
      }
    });
    console.log("[notifications.ts] Tauri onAction listener attached.");
  } catch (err) {
    console.error("[notifications.ts] Error during setupTauriNotifications:", err);
  }
}

async function fireTauriNotification(title: string, body: string, silent: boolean): Promise<void> {
  console.log("[notifications.ts] fireTauriNotification triggered:", { title, body, silent });
  try {
    await setupTauriNotifications();

    const { isPermissionGranted, requestPermission, sendNotification } =
      await import("@tauri-apps/plugin-notification");

    const granted = await isPermissionGranted();
    console.log("[notifications.ts] Tauri isPermissionGranted check result:", granted);

    if (!granted) {
      console.log("[notifications.ts] Permission not granted yet, calling requestPermission()...");
      const perm = await requestPermission();
      console.log("[notifications.ts] requestPermission() returned:", perm);
      if (perm !== "granted") {
        console.warn("[notifications.ts] Tauri notification dispatch aborted — permission denied or ignored:", perm);
        return;
      }
    }

    if (!silent) {
      // Trigger audio chime specifically for Tauri OS notifications since WinRT toasts in dev mode can be silent
      playInAppNotificationSound();
    }

    console.log("[notifications.ts] Executing notification dispatch in Tauri via IPC sendNotification...");
    try {
      // STRICTLY use Tauri's sendNotification IPC plugin.
      // Do NOT use window.Notification in Tauri because its native click handlers do not bind correctly to Tauri's unminimize/focus methods.
      sendNotification({
        title,
        body,
        actionTypeId: TAURI_ACTION_TYPE,
        sound: silent ? undefined : "default",
      });
      console.log("[notifications.ts] Dispatched via Tauri IPC sendNotification successfully!");
    } catch (notifErr) {
      console.error("[notifications.ts] Fatal error during Tauri sendNotification IPC:", notifErr);
    }
  } catch (err) {
    console.error("[notifications.ts] Fatal error inside fireTauriNotification:", err);
  }
}

// ── Web Notifications API ────────────────────────────────────────────────

async function fireWebNotification(title: string, body: string, silent: boolean): Promise<void> {
  console.log("[notifications.ts] fireWebNotification triggered:", { title, body, silent });
  const hasAPI = "Notification" in window;
  if (!hasAPI) {
    console.warn("[notifications.ts] Web Notification API not present in this browser/environment.");
    return;
  }
  
  console.log("[notifications.ts] Web Notification.permission state:", Notification.permission);

  if (Notification.permission !== "granted") {
    console.warn("[notifications.ts] Web notification aborted — Notification.permission is not 'granted'.");
    return;
  }

  try {
    // Note: Do NOT play synthesized audio here — web browsers already emit their own system alert tone.
    console.log("[notifications.ts] Dispatching new Web Notification...");
    const notif = new Notification(title, { body, silent });
    notif.onclick = (e): void => {
      console.log("[notifications.ts] Web Notification clicked");
      e.preventDefault();
      notif.close();
      window.focus();
      if (_activeNotificationCallback) {
        console.log("[notifications.ts] Executing navigation callback from Web Notification onclick");
        const cb = _activeNotificationCallback;
        _activeNotificationCallback = null;
        cb();
      }
    };
    console.log("[notifications.ts] Web Notification dispatched successfully!");
  } catch (err) {
    console.error("[notifications.ts] Error dispatching Web Notification:", err);
  }
}

// ── Public API ───────────────────────────────────────────────────────────

/**
 * Fire a job-match notification using the correct platform API.
 *
 * @param jobTitle - Job title shown in the notification body.
 * @param matchScore - Match score (0–100).
 * @param jobCount - Number of jobs found in this batch.
 * @param onClick - Optional navigation callback executed when the OS notification is explicitly clicked.
 * @param silent - If true, OS notification will not make a sound or popup (DND mode).
 */
export async function fireNotification(
  jobTitle: string,
  matchScore: number,
  jobCount: number = 1,
  onClick?: () => void,
  silent: boolean = false,
): Promise<void> {
  _activeNotificationCallback = onClick || null;
  const isMultiple = jobCount > 1;
  const title = isMultiple ? s.titleMultiple : s.title;
  const body = isMultiple
    ? s.bodyMultiple.replace("{count}", String(jobCount))
    : s.body.replace("{jobTitle}", jobTitle).replace("{score}", String(matchScore));

  const isTauri = "__TAURI__" in window;
  console.log("[notifications.ts] fireNotification routing decision:", { isTauri, title, body, jobCount, silent, hasOnClick: Boolean(onClick) });

  if (isTauri) {
    await fireTauriNotification(title, body, silent);
  } else {
    await fireWebNotification(title, body, silent);
  }
}
