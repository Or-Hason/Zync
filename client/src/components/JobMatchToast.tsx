import { useEffect } from "react";

import { en } from "@/i18n/en";
import styles from "./JobMatchToast.module.css";

const s = en.notifications;

interface JobMatchToastProps {
  /** Job title (used only when job_count === 1). */
  jobTitle: string;
  /** Match score (used only when job_count === 1). */
  matchScore: number;
  /** Total jobs found in this scan batch. */
  jobCount: number;
  /** Text on the action button (e.g. "View matches" or "View job"). Omit to hide. */
  actionLabel?: string;
  /** Called when the action button is clicked. */
  onAction?: () => void;
  /** Called when the toast is dismissed. */
  onDismiss: () => void;
  /**
   * Auto-dismiss delay in ms. Pass 0 to make the toast persistent
   * (only dismissed by user interaction).
   */
  duration?: number;
}

/**
 * In-app toast for job match notifications with an optional navigation action.
 *
 * - On the Explorer page: persistent (duration=0), no action button needed.
 * - On other pages: auto-dismiss after 8 s with a "View matches" action button.
 * - Single job override: action button reads "View job".
 */
export function JobMatchToast({
  jobTitle,
  matchScore,
  jobCount,
  actionLabel,
  onAction,
  onDismiss,
  duration = 0,
}: JobMatchToastProps): React.JSX.Element {
  const message =
    jobCount > 1
      ? s.toastExplorerMultiple.replace("{count}", String(jobCount))
      : s.toastExplorer
          .replace("{jobTitle}", jobTitle)
          .replace("{score}", String(matchScore));

  /* Auto-dismiss timer when duration > 0. */
  useEffect(() => {
    if (duration <= 0) return;
    const id = setTimeout(onDismiss, duration);
    return (): void => clearTimeout(id);
  }, [duration, onDismiss]);

  return (
    <div
      className={styles.toast}
      role="alert"
      aria-live="assertive"
      aria-label={message}
    >
      <span className={styles.message}>{message}</span>
      {actionLabel && onAction && (
        <button
          type="button"
          className={styles.action}
          onClick={(): void => {
            onAction();
            onDismiss();
          }}
          aria-label={actionLabel}
        >
          {actionLabel}
        </button>
      )}
      <button
        type="button"
        className={styles.close}
        onClick={onDismiss}
        aria-label={s.dismiss}
      >
        ×
      </button>
    </div>
  );
}
