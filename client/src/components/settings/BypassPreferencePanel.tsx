import { useState } from "react";
import { en } from "@/i18n/en";
import { useBypassPreference, useSetBypassPreference } from "@/api/settingsApi";
import type { BypassPreference } from "@/api/settingsApi";
import { Toast } from "@/components/resume/Toast";
import styles from "./BypassPreferencePanel.module.css";

const s = en.pages.settings.bypassPreference;

type ToastState = { message: string; kind: "success" | "error" } | null;

interface PreferenceOption {
  value: BypassPreference;
  label: string;
}

const OPTIONS: PreferenceOption[] = [
  { value: "ask",    label: s.ask },
  { value: "always", label: s.always },
  { value: "never",  label: s.never },
];

/**
 * Panel for selecting the blacklist bypass preference.
 * Selection is server-synced — no local state for the active value.
 * @returns The rendered bypass preference panel.
 */
export function BypassPreferencePanel(): React.JSX.Element {
  const { data: preference, isLoading, isError } = useBypassPreference();
  const { mutate: setPreference } = useSetBypassPreference();
  const [toast, setToast] = useState<ToastState>(null);

  function handleChange(value: BypassPreference): void {
    if (preference === value) return;
    setPreference(value, {
      onSuccess: () => setToast({ message: s.savedToast, kind: "success" }),
      onError: () => setToast({ message: en.common.error, kind: "error" }),
    });
  }

  return (
    <section className={styles.panel} aria-labelledby="bypass-pref-title">
      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={(): void => setToast(null)}
        />
      )}

      <div className={styles.panelHeader}>
        <h2 id="bypass-pref-title" className={styles.panelTitle}>{s.title}</h2>
        <p className={styles.panelSubtitle}>{s.subtitle}</p>
      </div>

      {isError ? (
        <p className={styles.errorState} role="alert">{en.common.error}</p>
      ) : (
        <div
          className={styles.segmented}
          role="radiogroup"
          aria-label={s.groupAriaLabel}
          aria-busy={isLoading}
        >
          {OPTIONS.map(({ value, label }) => (
            <label
              key={value}
              className={`${styles.segment} ${preference === value ? styles.segmentActive : ""} ${isLoading ? styles.segmentDisabled : ""}`}
              aria-label={label}
            >
              <input
                type="radio"
                className={styles.hiddenRadio}
                name="bypassPreference"
                value={value}
                checked={preference === value}
                disabled={isLoading}
                onChange={(): void => handleChange(value)}
                aria-label={label}
              />
              {label}
            </label>
          ))}
        </div>
      )}
    </section>
  );
}
