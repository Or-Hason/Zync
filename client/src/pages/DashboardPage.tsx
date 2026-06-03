import { en } from "@/i18n/en";
import styles from "./Page.module.css";

/** Dashboard placeholder — Phase 2 will populate with job listings and stats. */
export function DashboardPage(): React.JSX.Element {
  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>{en.pages.dashboard.title}</h1>
        <p className={styles.pageSubtitle}>{en.pages.dashboard.subtitle}</p>
      </header>
      <div className={styles.placeholder} aria-label="Dashboard content coming soon">
        {en.common.comingSoon}
      </div>
    </main>
  );
}
