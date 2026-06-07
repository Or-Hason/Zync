import { useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useActiveResume, useSetActiveResume } from "@/api/resumeApi";
import styles from "./ScorePlaceholder.module.css";

const s = en.pages.jobAdd.scorePlaceholder;

interface ScorePlaceholderProps {
  /** Triggers the scoring pipeline with the currently active resume. */
  onRequestScore: () => void;
  /** Navigate to the Resume Manager with returnTo state preserved. */
  onNavigateUpload: () => void;
  isScoringPending: boolean;
}

/**
 * Empty-state panel rendered inside JobCard when no match score exists.
 * Adapts to the user's resume state:
 *   - No resumes → upload prompt
 *   - Resumes exist, none active → inline native select (avoids overflow:hidden clipping)
 *   - Active resume selected → prominent Calculate button
 *   - Scoring in progress → spinner
 */
export function ScorePlaceholder({
  onRequestScore,
  onNavigateUpload,
  isScoringPending,
}: ScorePlaceholderProps): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();
  const { mutate: setActive } = useSetActiveResume();
  const [localSelectedId, setLocalSelectedId] = useState("");

  if (isScoringPending) {
    return (
      <div className={styles.placeholder} aria-live="polite">
        <div className={styles.spinner} role="status" aria-label={s.calculating} />
        <p className={styles.text}>{s.calculating}</p>
      </div>
    );
  }

  if (resumes.length === 0) {
    return (
      <div className={styles.placeholder}>
        <p className={styles.text}>{s.noResumeText}</p>
        <button
          className={styles.primaryBtn}
          onClick={onNavigateUpload}
          aria-label={s.uploadButton}
        >
          {s.uploadButton}
        </button>
      </div>
    );
  }

  if (!activeResume) {
    return (
      <div className={styles.placeholder}>
        <p className={styles.selectLabel}>{s.selectLabel}</p>
        <select
          className={styles.select}
          value={localSelectedId}
          onChange={(e): void => {
            const id = e.target.value;
            setLocalSelectedId(id);
            if (id) setActive(id);
          }}
          aria-label={s.selectLabel}
        >
          <option value="">— Select a resume —</option>
          {resumes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.version_name}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div className={styles.placeholder}>
      <button
        className={styles.calculateBtn}
        onClick={onRequestScore}
        aria-label={s.calculateButton}
      >
        {s.calculateButton}
      </button>
    </div>
  );
}
