/**
 * Scan-frequency selector sub-component extracted from AutoScanPanel.
 */

import { SCAN_FREQUENCY_CHOICES } from "@/api/settingsApi";
import type { ScanFrequencyHours } from "@/api/settingsApi";
import { en } from "@/i18n/en";
import styles from "./AutoScanPanel.module.css";

const s = en.pages.settings.autoScan;

/** Human-readable "Every N hour(s)" label for a frequency choice. */
function frequencyLabel(hours: number): string {
  const suffix = hours === 1 ? s.frequencyHourSuffix : s.frequencyHoursSuffix;
  return `${s.frequencyEveryPrefix} ${hours} ${suffix}`;
}

interface ScanFrequencyFieldProps {
  /** Currently persisted interval between automatic scans, in hours. */
  value: ScanFrequencyHours;
  /** Whether the selector is locked (mutation in-flight or auto-scan disabled). */
  disabled: boolean;
  /** Notify the parent of a newly selected frequency. */
  onChange: (hours: ScanFrequencyHours) => void;
}

/**
 * Labelled `<select>` listing every supported auto-scan interval.
 *
 * @param props - {@link ScanFrequencyFieldProps}
 * @returns The rendered scan-frequency field.
 */
export function ScanFrequencyField({
  value,
  disabled,
  onChange,
}: ScanFrequencyFieldProps): React.JSX.Element {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel} htmlFor="scan-frequency">
        {s.frequencyLabel}
      </label>
      <select
        id="scan-frequency"
        className={styles.select}
        value={value}
        disabled={disabled}
        onChange={(e): void =>
          onChange(Number(e.target.value) as ScanFrequencyHours)
        }
        aria-label={s.frequencyAriaLabel}
      >
        {SCAN_FREQUENCY_CHOICES.map((hours) => (
          <option key={hours} value={hours}>
            {frequencyLabel(hours)}
          </option>
        ))}
      </select>
    </div>
  );
}
