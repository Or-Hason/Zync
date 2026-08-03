/**
 * Cross-platform notification dispatcher and acoustic chime generator.
 *
 * Presents a single `fireNotification` call over three very different backends:
 * a custom Rust command on Windows, the Tauri plugin on other desktops, and the
 * browser Notifications API on the web. Click routing goes through genuine
 * platform events — nothing here polls or fakes focus.
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

/** Rust-side activation event. Must match `ACTIVATED_EVENT` in `notification.rs`. */
const TAURI_ACTIVATED_EVENT = "notification://activated";

let _tauriReady = false;
/** Holds the active navigation callback to execute when an OS notification is explicitly clicked. */
let _activeNotificationCallback: (() => void) | null = null;

/**
 * Subscribe once to native toast clicks. Idempotent.
 *
 * The plugin's `onAction` is deliberately not used: its Actions API is
 * documented as mobile-only, and no desktop code path ever emits the event it
 * listens for, so it can never fire here. Worse, the `registerActionTypes` call
 * that used to precede it invoked a command that does not exist on desktop, so
 * it threw and skipped the listener registration entirely.
 */
export async function setupTauriNotifications(): Promise<void> {
  if (_tauriReady) return;
  _tauriReady = true;

  try {
    const { listen } = await import("@tauri-apps/api/event");
    await listen(TAURI_ACTIVATED_EVENT, () => {
      // Rust has already unminimised and focused the window by this point.
      const cb = _activeNotificationCallback;
      _activeNotificationCallback = null;
      cb?.();
    });
  } catch (err) {
    console.error("[notifications.ts] Failed to subscribe to toast activation:", err);
    // Allow a later notification to retry the subscription.
    _tauriReady = false;
  }
}

/**
 * Show a native toast, preferring the path on which a click can reach us.
 *
 * `show_toast` is a custom Rust command that attaches a WinRT `Activated`
 * handler. It is Windows-only and reports failure elsewhere, so other desktops
 * fall through to the plugin — the toast still appears there, but clicking it
 * does nothing, which is an upstream limitation rather than a bug here.
 */
async function fireTauriNotification(title: string, body: string, silent: boolean): Promise<void> {
  await setupTauriNotifications();

  if (!silent) {
    // Our own chime: WinRT toasts are silent in some dev configurations.
    playInAppNotificationSound();
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("show_toast", { title, body, silent });
    return;
  } catch (err) {
    console.warn("[notifications.ts] Clickable toast unavailable, using plugin:", err);
  }

  await firePluginNotification(title, body, silent);
}

/** Plugin fallback for non-Windows desktops. Shows the toast; the click is inert. */
async function firePluginNotification(title: string, body: string, silent: boolean): Promise<void> {
  try {
    const { isPermissionGranted, requestPermission, sendNotification } =
      await import("@tauri-apps/plugin-notification");

    if (!(await isPermissionGranted())) {
      const perm = await requestPermission();
      if (perm !== "granted") {
        console.warn("[notifications.ts] Notification permission not granted:", perm);
        return;
      }
    }

    sendNotification({ title, body, sound: silent ? undefined : "default" });
  } catch (err) {
    console.error("[notifications.ts] Plugin notification dispatch failed:", err);
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
