import { en } from "@/i18n/en";
import type { ResumeStructuredData } from "@/types/resume";
import styles from "./Shared.module.css";

const rm = en.pages.resumeManager;

interface MetaPanelProps {
  versionName: string;
  data: ResumeStructuredData;
  versionNameError: boolean;
  onVersionNameChange: (value: string) => void;
  onFieldChange: (field: ScalarKey, value: string) => void;
}

/** Keys in ResumeStructuredData whose values are string | null. */
export type ScalarKey =
  | "full_name" | "current_role" | "target_role" | "email" | "phone"
  | "location" | "linkedin_url" | "github_url" | "portfolio_url" | "summary";

type ScalarField = {
  key: ScalarKey;
  label: string;
  multiline?: boolean;
};

const SCALAR_FIELDS: ScalarField[] = [
  { key: "full_name",     label: rm.fields.fullName },
  { key: "current_role",  label: rm.fields.currentRole },
  { key: "target_role",   label: rm.fields.targetRole },
  { key: "email",         label: rm.fields.email },
  { key: "phone",         label: rm.fields.phone },
  { key: "location",      label: rm.fields.location },
  { key: "linkedin_url",  label: rm.fields.linkedinUrl },
  { key: "github_url",    label: rm.fields.githubUrl },
  { key: "portfolio_url", label: rm.fields.portfolioUrl },
  { key: "summary",       label: rm.fields.summary, multiline: true },
];

/**
 * Left panel: version name + all scalar metadata fields.
 * @param versionName - Current version label (required).
 * @param data - Full structured data object.
 * @param versionNameError - Whether to show required-field warning.
 * @param onVersionNameChange - Callback when version name changes.
 * @param onFieldChange - Callback when any structured_data scalar field changes.
 */
export function MetaPanel({ versionName, data, versionNameError, onVersionNameChange, onFieldChange }: MetaPanelProps): React.JSX.Element {
  return (
    <div className={styles.panel} aria-label="Resume metadata fields">
      {/* Version name — not part of structured_data but required */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="version-name">
          {rm.versionNameLabel}
        </label>
        <input
          id="version-name"
          className={styles.input}
          value={versionName}
          onChange={(e): void => onVersionNameChange(e.target.value)}
          aria-label={rm.versionNameLabel}
          aria-required="true"
          aria-invalid={versionNameError}
        />
        {versionNameError && (
          <span className={styles.validationMsg} role="alert">{rm.versionNameRequired}</span>
        )}
      </div>

      {SCALAR_FIELDS.map(({ key, label, multiline }) => {
        const strValue = (data[key] as string | null) ?? "";
        return (
          <div key={key} className={styles.field}>
            <label className={styles.label} htmlFor={`field-${key}`}>{label}</label>
            {multiline ? (
              <textarea
                id={`field-${key}`}
                className={styles.textarea}
                value={strValue}
                onChange={(e): void => onFieldChange(key, e.target.value)}
                aria-label={label}
              />
            ) : (
              <input
                id={`field-${key}`}
                className={styles.input}
                value={strValue}
                onChange={(e): void => onFieldChange(key, e.target.value)}
                aria-label={label}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
