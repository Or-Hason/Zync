/**
 * Mounts the SSE notification stream and routes job-match events to the
 * platform notification dispatcher.
 *
 * Must be called once in the root layout component (App.tsx).
 */

import { useEffect } from "react";

import { fireNotification, setupTauriNotifications } from "@/services/notifications";

interface JobMatchPayload {
  job_id: string;
  job_title: string;
  match_score: number;
}

const SSE_URL = "/api/notifications/stream";

export function useNotifications(): void {
  useEffect(() => {
    if ("__TAURI__" in window) {
      void setupTauriNotifications();
    }

    const es = new EventSource(SSE_URL);

    es.addEventListener("job_match", (e: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(e.data) as JobMatchPayload;
        void fireNotification(payload.job_title, payload.match_score);
      } catch {
        // Malformed event payload — silently skip.
      }
    });

    // EventSource reconnects automatically on error; no manual retry needed.
    es.onerror = (): void => undefined;

    return (): void => es.close();
  }, []);
}
