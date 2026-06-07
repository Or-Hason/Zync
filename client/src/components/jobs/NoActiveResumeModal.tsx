import { useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useSetActiveResume } from "@/api/resumeApi";
import type { ResumeListItem } from "@/types/resume";
import styles from "./NoActiveResumeModal.module.css";

const s = en.pages.jobAdd.noActiveResumeModal;

interface NoActiveResumeModalProps {
  /** Dismiss the modal and show the job card without a score. */
  onViewJobOnly: () => void;
  /** Navigate to Resume Manager with returnTo state preserved. */
  onNavigateUpload: () => void;
  /**
   * Called after the selected resume is successfully set as active.
   * The parent then triggers the scoring pipeline.
   */
  onCalculateScore: () => void;
  isScoringPending: boolean;
}

/**
 * Intercept dialog shown when a job is parsed but no active resume is found.
 * Lets the user select an existing resume to score against, upload a new one,
 * or dismiss and view the job details without a score.
 */
export function NoActiveResumeModal({
  onViewJobOnly,
  onNavigateUpload,
  onCalculateScore,
  isScoringPending,
}: NoActiveResumeModalProps): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { mutate: setActive, isPending: isSettingActive } = useSetActiveResume();
  const [selectedId, setSelectedId] = useState("");

  const isLoading = isScoringPending || isSettingActive;

  function handleCalculate(): void {
    if (!selectedId) return;
    setActive(selectedId, { onSuccess: onCalculateScore });
  }

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="no-resume-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="no-resume-modal-title" className={styles.title}>
          {s.title}
        </h2>
        <p className={styles.message}>{s.message}</p>

        {resumes.length > 0 && (
          <div className={styles.selectorGroup}>
            <select
              className={styles.select}
              value={selectedId}
              onChange={(e): void => setSelectedId(e.target.value)}
              disabled={isLoading}
              aria-label={s.selectPlaceholder}
            >
              <option value="">{s.selectPlaceholder}</option>
              {resumes.map((r: ResumeListItem) => (
                <option key={r.id} value={r.id}>
                  {r.version_name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className={styles.actions}>
          <button
            className={styles.buttonSecondary}
            onClick={onViewJobOnly}
            disabled={isLoading}
            aria-label={s.viewJobOnly}
          >
            {s.viewJobOnly}
          </button>
          <button
            className={styles.buttonSecondary}
            onClick={onNavigateUpload}
            disabled={isLoading}
            aria-label={s.uploadResume}
          >
            {s.uploadResume}
          </button>
          {resumes.length > 0 && selectedId && (
            <button
              className={styles.buttonPrimary}
              onClick={handleCalculate}
              disabled={isLoading}
              aria-busy={isLoading}
              aria-label={isLoading ? s.calculating : s.calculateScore}
            >
              {isLoading ? s.calculating : s.calculateScore}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
