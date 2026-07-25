/**
 * Mounts the SSE notification stream and routes job-match events to the
 * correct notification surface based on the user's current context:
 *
 * 1. **App backgrounded** (`document.hidden`): native OS notification.
 * 2. **On Explorer page**: persistent in-app toast (no auto-dismiss).
 * 3. **On any other page**: auto-dismiss toast with a "View matches" link.
 * 4. **Single job override**: clicking any notification navigates to `/jobs/:id`.
 *
 * Must be called once in the root layout component (App.tsx).
 */

import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { en } from "@/i18n/en";
import { fireNotification } from "@/services/notifications";

const s = en.notifications;

interface JobMatchPayload {
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

/**
 * Determine the navigation target for a notification action.
 * Single match → `/jobs/:id`; multiple → `/explorer`.
 */
function resolveTarget(payload: JobMatchPayload): string {
  return payload.job_count === 1
    ? `/jobs/${payload.job_id}`
    : EXPLORER_PATH;
}

export function useNotifications(): {
  toast: JobMatchToastState | null;
  dismissToast: () => void;
  navigateToAction: () => void;
} {
  const location = useLocation();
  const navigate = useNavigate();
  const [toast, setToast] = useState<JobMatchToastState | null>(null);

  const dismissToast = useCallback((): void => setToast(null), []);

  const navigateToAction = useCallback((): void => {
    if (!toast) return;
    navigate(toast.actionPath);
    setToast(null);
  }, [toast, navigate]);

  useEffect(() => {
    if ("__TAURI__" in window) {
      void import("@/services/notifications").then((m) =>
        m.setupTauriNotifications(),
      );
    }

    const es = new EventSource(SSE_URL);

    es.addEventListener("job_match", (e: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(e.data) as JobMatchPayload;

        // DND mode: silently discard the event entirely.
        if (payload.silent) return;

        // 1) App backgrounded → native notification only.
        if (document.hidden) {
          void fireNotification(
            payload.job_title,
            payload.match_score,
            payload.job_count,
          );
          return;
        }

        // 2) App visible → in-app toast.
        const isOnExplorer = location.pathname === EXPLORER_PATH;
        const target = resolveTarget(payload);
        const isSingle = payload.job_count === 1;

        if (isOnExplorer) {
          // Persistent toast, no navigation action needed (user is already here).
          setToast({
            jobTitle: payload.job_title,
            matchScore: payload.match_score,
            jobCount: payload.job_count,
            jobId: payload.job_id,
            actionLabel: isSingle ? s.viewJob : "",
            actionPath: target,
            duration: 0,
          });
        } else {
          // Auto-dismiss toast with "View matches" / "View job" action.
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
      } catch {
        // Malformed event payload — silently skip.
      }
    });

    es.onerror = (): void => undefined;

    return (): void => es.close();
    // location.pathname is intentionally captured via closure so the handler
    // always has the latest route context when an SSE event fires.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return { toast, dismissToast, navigateToAction };
}
