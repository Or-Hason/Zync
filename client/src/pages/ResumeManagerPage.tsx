import { en } from "@/i18n/en";
import styles from "./Page.module.css";

/** Resume Manager placeholder — fully implemented in FE-02. */
export function ResumeManagerPage(): React.JSX.Element {
  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>{en.pages.resumeManager.title}</h1>
        <p className={styles.pageSubtitle}>{en.pages.resumeManager.subtitle}</p>
      </header>
      <div className={styles.placeholder} aria-label="Resume Manager content coming soon">
        {en.common.comingSoon}
      </div>
    </main>
  );
}
