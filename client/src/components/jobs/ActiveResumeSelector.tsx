import { useEffect, useRef, useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useActiveResume, useSetActiveResume } from "@/api/resumeApi";
import type { ResumeListItem } from "@/types/resume";
import styles from "./ActiveResumeSelector.module.css";

const s = en.pages.jobAdd.activeResumeSelector;

interface Props {
  layout?: "row" | "column";
}

/**
 * Selector widget for choosing the active resume.
 * Shows current active resume and lists all available resumes.
 * @param layout - "row" (default) places label inline; "column" stacks label above dropdown, centered.
 */
export function ActiveResumeSelector({ layout = "row" }: Props): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();
  const { mutate: setActive } = useSetActiveResume();
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  /**
   * Dismiss the menu on an outside click or Escape.
   *
   * Bound on `pointerdown` rather than `click` so the menu closes on press —
   * a `click` listener would fire after the pressed element had already acted,
   * leaving the menu open over the page for the duration of the interaction.
   */
  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent): void {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") setIsOpen(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  function handleSelect(resume: ResumeListItem): void {
    setActive(resume.id);
    setIsOpen(false);
  }

  const displayName = activeResume?.version_name || s.noResume;

  return (
    <div
      ref={rootRef}
      className={`${styles.selector} ${layout === "column" ? styles.selectorColumn : ""}`}
    >
      <label className={`${styles.label} ${layout === "column" ? styles.labelColumn : ""}`}>{s.label}</label>
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
                  title={resume.version_name}
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
