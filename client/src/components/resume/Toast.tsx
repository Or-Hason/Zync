import { useEffect } from "react";
import styles from "./Toast.module.css";

type ToastKind = "success" | "error";

interface ToastProps {
  message: string;
  kind: ToastKind;
  /** Auto-dismiss after this many ms (default 3500). Pass 0 to disable. */
  duration?: number;
  onDismiss: () => void;
}

/**
 * Ephemeral status toast displayed at the top-right of the viewport.
 * @param message - Text to display.
 * @param kind - Visual variant: "success" or "error".
 * @param duration - Auto-dismiss delay in ms.
 * @param onDismiss - Called when the toast should be removed.
 */
export function Toast({ message, kind, duration = 3500, onDismiss }: ToastProps): React.JSX.Element {
  useEffect(() => {
    if (duration <= 0) return;
    const id = setTimeout(onDismiss, duration);
    return (): void => clearTimeout(id);
  }, [duration, onDismiss]);

  return (
    <div
      className={`${styles.toast} ${kind === "error" ? styles.error : styles.success}`}
      role="status"
      aria-live="polite"
      aria-label={message}
    >
      <span className={styles.message}>{message}</span>
      <button
        className={styles.close}
        onClick={onDismiss}
        aria-label="Dismiss notification"
      >
        ×
      </button>
    </div>
  );
}
