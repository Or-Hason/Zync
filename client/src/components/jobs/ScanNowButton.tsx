import { en } from "@/i18n/en";
import { fetchScanSettings, SETTINGS_KEYS, useTriggerScan } from "@/api/settingsApi";
import type { ScanSettings } from "@/api/settingsApi";
import { useQuery } from "@tanstack/react-query";
import styles from "./ScanNowButton.module.css";

const s = en.pages.jobAdd.scanNow;

/**
 * "Scan for Jobs" button for the Add Job page. Triggers an immediate background
 * scan regardless of the auto-scan schedule. Polls the scan status every 2 s
 * while running so the button stays disabled and shows a spinner until done.
 */
export function ScanNowButton(): React.JSX.Element {
  const { data: settings } = useQuery<ScanSettings>({
    queryKey: SETTINGS_KEYS.scan,
    queryFn: fetchScanSettings,
    refetchInterval: (query) => (query.state.data?.scan_in_progress ? 2000 : false),
  });

  const { mutate: trigger, isPending, error } = useTriggerScan();

  const isScanning = isPending || (settings?.scan_in_progress ?? false);
  const errorMsg = error
    ? error.status === 409
      ? s.errorConflict
      : error.status === 400
        ? s.errorNoResume
        : null
    : null;

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.btn}
        disabled={isScanning}
        aria-label={isScanning ? s.scanningAriaLabel : s.ariaLabel}
        onClick={(): void => trigger()}
      >
        {isScanning && <span className={styles.spinner} aria-hidden="true" />}
        {isScanning ? s.scanning : s.label}
      </button>
      {errorMsg && (
        <p className={styles.error} role="alert">
          {errorMsg}
        </p>
      )}
    </div>
  );
}
