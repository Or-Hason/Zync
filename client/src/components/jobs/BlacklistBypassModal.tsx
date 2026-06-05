import { useState } from "react";
import { en } from "@/i18n/en";
import styles from "./BlacklistBypassModal.module.css";

const s = en.pages.jobAdd.blacklistModal;

interface BlacklistBypassModalProps {
  keyword: string;
  onScoreAnyway: (remember: boolean) => void;
  onDiscard: () => void;
}

/**
 * Modal shown when a blacklist hit occurs with "Ask before" preference.
 * Allows user to score the job anyway or discard it, with a "Remember my choice" checkbox.
 * @param keyword - The matched blacklist keyword.
 * @param onScoreAnyway - Called when user clicks "Score Anyway".
 * @param onDiscard - Called when user clicks "Discard".
 */
export function BlacklistBypassModal({
  keyword,
  onScoreAnyway,
  onDiscard,
}: BlacklistBypassModalProps): React.JSX.Element {
  const [remember, setRemember] = useState(false);

  return (
    <div className={styles.overlay}>
      <div className={styles.modal} role="alertdialog" aria-labelledby="modal-title">
        <h2 id="modal-title" className={styles.title}>{s.title}</h2>

        <p className={styles.message}>
          {s.messagePrefix} <strong>{keyword}</strong>
        </p>

        <label className={styles.checkboxWrap} title={s.rememberTooltip}>
          <input
            type="checkbox"
            className={styles.checkbox}
            checked={remember}
            onChange={(e): void => setRemember(e.target.checked)}
            aria-label={s.rememberChoice}
          />
          <span className={styles.checkboxLabel}>{s.rememberChoice}</span>
        </label>

        <div className={styles.actions}>
          <button
            className={styles.buttonDiscard}
            onClick={onDiscard}
            aria-label={s.discard}
          >
            {s.discard}
          </button>
          <button
            className={styles.buttonScore}
            onClick={(): void => onScoreAnyway(remember)}
            aria-label={s.scoreAnyway}
          >
            {s.scoreAnyway}
          </button>
        </div>
      </div>
    </div>
  );
}
