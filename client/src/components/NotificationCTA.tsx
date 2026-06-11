import { useState } from "react";
import { en } from "@/i18n/en";
import { useScanSettings } from "@/api/settingsApi";
import styles from "./NotificationCTA.module.css";

const s = en.notifications;
export const DISMISSED_KEY = "zync:notif-cta-dismissed";

const isWeb = !("__TAURI__" in window);
const hasNotifApi = "Notification" in window;

/**
 * Dismissible CTA banner prompting the user to enable browser notifications.
 * Renders globally (in root layout) only when: web mode, auto_scan is on, and
 * permission is still 'default'. Permanently suppressed via localStorage when
 * the user dismisses with "Don't ask me again" checked.
 */
export function NotificationCTA(): React.JSX.Element | null {
  const { data: settings } = useScanSettings();
  const [permission, setPermission] = useState<NotificationPermission>(
    hasNotifApi ? Notification.permission : "denied",
  );
  const [dismissed, setDismissed] = useState(false);
  const [dontAskChecked, setDontAskChecked] = useState(false);
  const [persistentlyDismissed] = useState(
    () => localStorage.getItem(DISMISSED_KEY) === "true",
  );

  if (
    !isWeb ||
    !hasNotifApi ||
    permission !== "default" ||
    !settings?.auto_scan_enabled ||
    dismissed ||
    persistentlyDismissed
  ) {
    return null;
  }

  async function handleEnable(): Promise<void> {
    const result = await Notification.requestPermission();
    setPermission(result);
    setDismissed(true);
  }

  function handleDismiss(): void {
    if (dontAskChecked) localStorage.setItem(DISMISSED_KEY, "true");
    setDismissed(true);
  }

  return (
    <div className={styles.banner} role="alert" aria-live="polite">
      <span className={styles.message}>{s.ctaBanner}</span>
      <div className={styles.actions}>
        <label className={styles.checkboxLabel}>
          <input
            type="checkbox"
            checked={dontAskChecked}
            onChange={(e): void => setDontAskChecked(e.target.checked)}
          />
          {s.dontAskAgain}
        </label>
        <button
          type="button"
          className={styles.enableBtn}
          onClick={(): void => { void handleEnable(); }}
        >
          {s.enableBtn}
        </button>
        <button
          type="button"
          className={styles.dismissBtn}
          onClick={handleDismiss}
          aria-label={s.dismiss}
        >
          ×
        </button>
      </div>
    </div>
  );
}
