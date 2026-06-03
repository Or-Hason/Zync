import { en } from "@/i18n/en";
import styles from "./Page.module.css";

/** Settings placeholder — Phase 3 will expose user preferences. */
export function SettingsPage(): React.JSX.Element {
  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>{en.pages.settings.title}</h1>
        <p className={styles.pageSubtitle}>{en.pages.settings.subtitle}</p>
      </header>
      <div className={styles.placeholder} aria-label="Settings content coming soon">
        {en.common.comingSoon}
      </div>
    </main>
  );
}
