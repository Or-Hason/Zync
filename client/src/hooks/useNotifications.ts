/**
 * Mounts the SSE notification stream and routes job-match events to the
 * correct notification surface based on the user's current context:
 *
 * **Backgrounded / unfocused** (`document.hidden` OR `!document.hasFocus()`):
 *   → Native OS notification (Tauri plugin on desktop, Web Notification API on web).
 *
 * **Foreground & focused**:
 *   → In-app toast: persistent (no auto-dismiss) on the Explorer page;
 *     auto-dismiss after 8 s with a navigation link on all other pages.
 *
 * **Single-job override**: all click targets navigate to `/jobs/:id`.
 *
 * Must be called once in the root layout component (App.tsx).
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { en } from "@/i18n/en";
import {
  fireNotification,
  playInAppNotificationSound,
  setupTauriNotifications,
} from "@/services/notifications";

const s = en.notifications;

export interface JobMatchPayload {
  job_id: string;
  job_title: string;
  match_score: number;
  job_count: number;
  silent: boolean;
}

/** State exposed to App.tsx so it can render the in-app toast. */
export interface JobMatchToastState {
  jobTitle: string;
  matchScore: number;
  jobCount: number;
  jobId: string;
  /** Label for the action button. Empty string → no button. */
  actionLabel: string;
  /** Where the action button navigates. */
  actionPath: string;
  /** Auto-dismiss ms. 0 = persistent. */
  duration: number;
}

const SSE_URL = "/api/notifications/stream";
const EXPLORER_PATH = "/explorer";
const AUTO_DISMISS_MS = 8_000;
const TEST_EVENT_NAME = "test_job_match";

/**
 * Returns true when the app should be treated as "out of view" for the user.
 *
 * Uses both `document.hidden` (tab/window switched away) and
 * `document.hasFocus()` (window exists but lost OS-level focus, e.g.
 * user alt-tabbed or is in split-screen with another app active).
 */
function isAppBackgrounded(): boolean {
  const isHidden = document.hidden;
  const hasFocus = typeof document.hasFocus === "function" ? document.hasFocus() : true;
  return isHidden || !hasFocus;
}

/**
 * Determine the navigation target for a notification action.
 * Single match → `/jobs/:id`; multiple → `/explorer?is_new=true&is_unread=true`.
 *
 * @param payload - The SSE job match event payload.
 * @returns The route path to navigate to on action.
 */
function resolveTarget(payload: JobMatchPayload): string {
  return payload.job_count === 1
    ? `/jobs/${payload.job_id}`
    : `${EXPLORER_PATH}?is_new=true&is_unread=true`;
}

/**
 * Helper to dispatch a simulated notification event from any UI component (e.g., Settings)
 * to test the notification pipeline without hitting real backend AI scanning.
 *
 * @param payload - The test payload to broadcast to the notification listener.
 */
export function dispatchTestNotification(payload: JobMatchPayload): void {
  window.dispatchEvent(new CustomEvent<JobMatchPayload>(TEST_EVENT_NAME, { detail: payload }));
}

export function useNotifications(): {
  toast: JobMatchToastState | null;
  dismissToast: () => void;
  navigateToAction: () => void;
} {
  const location = useLocation();
  const navigate = useNavigate();
  const [toast, setToast] = useState<JobMatchToastState | null>(null);

  // Keep a stable ref to the latest pathname so the global SSE connection never
  // needs to be torn down and re-established when navigating between pages.
  const pathnameRef = useRef<string>(location.pathname);
  useEffect(() => {
    pathnameRef.current = location.pathname;
  }, [location.pathname]);

  const dismissToast = useCallback((): void => setToast(null), []);

  const navigateToAction = useCallback((): void => {
    if (!toast) return;
    navigate(toast.actionPath);
    setToast(null);
  }, [toast, navigate]);

  useEffect(() => {
    console.log("[useNotifications] Initializing global notification listener...");
    if ("__TAURI__" in window) {
      console.log("[useNotifications] Tauri environment detected; calling setupTauriNotifications()");
      void setupTauriNotifications();
    }

    const handleJobMatch = (payload: JobMatchPayload): void => {
      console.log("SSE Event received", payload);

      // DND mode: do not discard the event!
      // We process it normally, but pass the `silent` flag down so it mutes
      // the in-app chime and Native OS popup/sound.
      if (payload.silent) {
        console.log("[useNotifications] DND active: processing event silently.");
      }

      const backgrounded = isAppBackgrounded();
      console.log("Visibility state:", backgrounded, {
        documentHidden: document.hidden,
        hasFocus: typeof document.hasFocus === "function" ? document.hasFocus() : "unknown",
      });

      const target = resolveTarget(payload);

      // ── Backgrounded / unfocused → Native OS notification ──────────────
      if (backgrounded) {
        console.log("Dispatching Native...", payload);
        void fireNotification(
          payload.job_title,
          payload.match_score,
          payload.job_count,
          () => {
            console.log("[useNotifications] OS Notification clicked -> navigating to:", target);
            navigate(target);
          },
          payload.silent,
        );
        return;
      }

      // ── Foregrounded & focused → In-app toast ──────────────────────────
      console.log("Dispatching Toast...", payload);
      if (!payload.silent) {
        playInAppNotificationSound();
      }
      const isOnExplorer = pathnameRef.current === EXPLORER_PATH;
      const isSingle = payload.job_count === 1;

      if (isOnExplorer) {
        // Persistent toast — user is already on the Explorer page.
        setToast({
          jobTitle: payload.job_title,
          matchScore: payload.match_score,
          jobCount: payload.job_count,
          jobId: payload.job_id,
          actionLabel: isSingle ? s.viewJob : s.refreshNewUnread,
          actionPath: target,
          duration: 0,
        });
      } else {
        // Auto-dismiss toast with navigation action.
        setToast({
          jobTitle: payload.job_title,
          matchScore: payload.match_score,
          jobCount: payload.job_count,
          jobId: payload.job_id,
          actionLabel: isSingle ? s.viewJob : s.viewMatches,
          actionPath: target,
          duration: AUTO_DISMISS_MS,
        });
      }
    };

    // 1) Listen to real SSE stream
    const es = new EventSource(SSE_URL);
    es.onopen = (): void => console.log("[useNotifications] SSE connection opened cleanly:", SSE_URL);
    es.onerror = (err): void => console.error("[useNotifications] SSE connection error/retry:", err);

    es.addEventListener("job_match", (e: MessageEvent<string>) => {

      try {
        const payload = JSON.parse(e.data) as JobMatchPayload;
        handleJobMatch(payload);
      } catch (err) {
        console.error("[useNotifications] Failed to parse SSE event data:", err, e.data);
      }
    });

    // 2) Listen to simulated test trigger event from Settings UI
    const handleTestEvent = (e: Event): void => {
      const detail = (e as CustomEvent<JobMatchPayload>).detail;
      if (detail) {
        console.log("[useNotifications] Simulated Test Notification event detected");
        handleJobMatch(detail);
      }
    };
    window.addEventListener(TEST_EVENT_NAME, handleTestEvent);

    return (): void => {
      console.log("[useNotifications] Cleaning up SSE connection and event listeners");
      es.close();
      window.removeEventListener(TEST_EVENT_NAME, handleTestEvent);
    };
    // Empty dependency array ensures we mount ONCE globally without resetting across route changes.
  }, [navigate]);

  return { toast, dismissToast, navigateToAction };
}
