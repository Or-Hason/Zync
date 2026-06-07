import { Link } from "react-router-dom";
import { en } from "@/i18n/en";
import styles from "./NoActiveResumePrompt.module.css";

const s = en.pages.jobAdd.noActiveResume;

/**
 * Inline prompt shown when no active resume is selected.
 * Includes a link to the Resume Manager page.
 */
export function NoActiveResumePrompt(): React.JSX.Element {
  return (
    <div className={styles.prompt} role="alert">
      <span className={styles.icon}>⚠</span>
      <div className={styles.content}>
        <p className={styles.message}>{s.prompt}</p>
        <Link to="/resumes" className={styles.link}>
          {s.linkText}
        </Link>
      </div>
    </div>
  );
}
