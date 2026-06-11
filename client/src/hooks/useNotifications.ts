/**
 * Mounts the SSE notification stream and routes job-match events to the
 * platform notification dispatcher. Also listens for the custom window event
 * that the notification click handler emits and navigates to the job detail page.
 *
 * Must be called once in the root layout component (App.tsx).
 */

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { fireNotification, setupTauriNotifications } from "@/services/notifications";

interface JobMatchPayload {
  job_id: string;
  job_title: string;
  match_score: number;
}

const SSE_URL = "/api/notifications/stream";

export function useNotifications(): void {
  const navigate = useNavigate();

  // Handle navigation triggered by notification clicks (both Tauri and Web).
  useEffect(() => {
    if ("__TAURI__" in window) {
      void setupTauriNotifications();
    } else if ("Notification" in window && Notification.permission === "default") {
      // Proactively request browser notification permission on first mount.
      void Notification.requestPermission();
    }

    function handleNavEvent(e: Event): void {
      const jobId = (e as CustomEvent<{ jobId: string }>).detail.jobId;
      navigate(`/jobs/${jobId}`);
    }

    window.addEventListener("zync:navigate-job", handleNavEvent);
    return (): void => window.removeEventListener("zync:navigate-job", handleNavEvent);
  }, [navigate]);

  // Open the SSE stream and dispatch a notification for each job_match event.
  useEffect(() => {
    const es = new EventSource(SSE_URL);

    es.addEventListener("job_match", (e: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(e.data) as JobMatchPayload;
        void fireNotification(payload.job_title, payload.match_score, payload.job_id);
      } catch {
        // Malformed event payload — silently skip.
      }
    });

    // EventSource reconnects automatically on error; no manual retry needed.
    es.onerror = (): void => undefined;

    return (): void => es.close();
  }, []);
}
