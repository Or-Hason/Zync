/**
 * Toast and fetch-state region extracted from AutoScanPanel.
 */

import { en } from "@/i18n/en";
import { Toast } from "@/components/resume/Toast";
import styles from "./AutoScanPanel.module.css";

const s = en.pages.settings.autoScan;

/** Transient feedback banner state owned by the parent panel. */
export type ToastState = { message: string; kind: "success" | "error" } | null;

interface ScanStatusRegionProps {
  /** Active toast, or `null` when no feedback is being shown. */
  toast: ToastState;
  /** Clears the parent's toast state. */
  onDismissToast: () => void;
  /** Whether the initial scan-settings fetch is still in flight. */
  isLoading: boolean;
  /** Whether the scan-settings fetch failed. */
  isError: boolean;
}

/**
 * Renders the panel's transient feedback: the save/error toast plus the
 * loading and error placeholders shown while the scan-settings request
 * resolves. The toast is fixed-position, so its placement within this
 * fragment is independent of the surrounding document flow.
 *
 * @param props - {@link ScanStatusRegionProps}
 * @returns The rendered status region.
 */
export function ScanStatusRegion({
  toast,
  onDismissToast,
  isLoading,
  isError,
}: ScanStatusRegionProps): React.JSX.Element {
  return (
    <>
      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={onDismissToast}
        />
      )}

      {isLoading && (
        <p className={styles.stateText} aria-busy="true">{s.loading}</p>
      )}

      {isError && (
        <p className={styles.errorState} role="alert">{s.fetchError}</p>
      )}
    </>
  );
}
