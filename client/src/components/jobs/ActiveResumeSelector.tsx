import { useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useActiveResume, useSetActiveResume } from "@/api/resumeApi";
import type { ResumeListItem } from "@/types/resume";
import styles from "./ActiveResumeSelector.module.css";

const s = en.pages.jobAdd.activeResumeSelector;

/**
 * Selector widget for choosing the active resume.
 * Shows current active resume and lists all available resumes.
 */
export function ActiveResumeSelector(): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();
  const { mutate: setActive } = useSetActiveResume();
  const [isOpen, setIsOpen] = useState(false);

  function handleSelect(resume: ResumeListItem): void {
    setActive(resume.id);
    setIsOpen(false);
  }

  const displayName = activeResume?.version_name || s.noResume;

  return (
    <div className={styles.selector}>
      <label className={styles.label}>{s.label}</label>
      <div className={styles.dropdown}>
        <button
          className={styles.button}
          onClick={(): void => setIsOpen(!isOpen)}
          aria-label={s.selectAriaLabel}
          aria-expanded={isOpen}
        >
          <span className={styles.buttonText}>{displayName}</span>
          <span className={styles.buttonArrow}>⌄</span>
        </button>

        {isOpen && (
          <div className={styles.menu} role="listbox">
            {resumes.length === 0 ? (
              <div className={styles.menuEmpty}>{en.pages.resumeManager.noResumes}</div>
            ) : (
              resumes.map((resume) => (
                <button
                  key={resume.id}
                  className={`${styles.menuItem} ${activeResume?.id === resume.id ? styles.menuItemActive : ""}`}
                  onClick={(): void => handleSelect(resume)}
                  role="option"
                  aria-selected={activeResume?.id === resume.id}
                >
                  {resume.version_name}
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
