import { useState } from "react";
import { en } from "@/i18n/en";
import styles from "./NotificationBlockedBanner.module.css";

const s = en.notifications;

/**
 * One-time dismissible info banner shown in web mode when the user has
 * explicitly denied notification permission. Not rendered in Tauri mode or
 * when permission is `default` (not yet asked) or `granted`.
 */
export function NotificationBlockedBanner(): React.JSX.Element | null {
  const [dismissed, setDismissed] = useState(false);

  if (
    dismissed ||
    "__TAURI__" in window ||
    !("Notification" in window) ||
    Notification.permission !== "denied"
  ) {
    return null;
  }

  return (
    <div className={styles.banner} role="alert" aria-live="polite">
      <span className={styles.message}>{s.blockedBanner}</span>
      <button
        className={styles.dismissBtn}
        onClick={(): void => setDismissed(true)}
        aria-label={s.blockedBannerDismiss}
        type="button"
      >
        {s.blockedBannerDismiss}
      </button>
    </div>
  );
}
