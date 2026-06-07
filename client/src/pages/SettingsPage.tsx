import { en } from "@/i18n/en";
import { BlacklistPanel } from "@/components/settings/BlacklistPanel";
import { BypassPreferencePanel } from "@/components/settings/BypassPreferencePanel";
import pageStyles from "./Page.module.css";
import styles from "./SettingsPage.module.css";

const s = en.pages.settings;

/** Settings page: blacklist keyword management and bypass preference. */
export function SettingsPage(): React.JSX.Element {
  return (
    <main className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <h1 className={pageStyles.pageTitle}>{s.title}</h1>
        <p className={pageStyles.pageSubtitle}>{s.subtitle}</p>
      </header>

      <div className={styles.panels}>
        <BlacklistPanel />
        <BypassPreferencePanel />
      </div>
    </main>
  );
}
