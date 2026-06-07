import { NavLink } from "react-router-dom";
import { en } from "@/i18n/en";
import styles from "./Sidebar.module.css";

interface NavItem {
  to: string;
  label: string;
  ariaLabel: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",         label: en.nav.dashboard,     ariaLabel: "Navigate to Dashboard" },
  { to: "/jobs/add", label: en.nav.addJob,        ariaLabel: "Navigate to Add Job" },
  { to: "/resumes",  label: en.nav.resumeManager, ariaLabel: "Navigate to Resume Manager" },
  { to: "/settings", label: en.nav.settings,      ariaLabel: "Navigate to Settings" },
];

/** Persistent left-side navigation sidebar. */
export function Sidebar(): React.JSX.Element {
  return (
    <aside className={styles.sidebar} aria-label="Main navigation">
      <div className={styles.brand} aria-label={en.app.name}>
        <span className={styles.brandName}>{en.app.name}</span>
      </div>

      <nav>
        <ul className={styles.navList} role="list">
          {NAV_ITEMS.map(({ to, label, ariaLabel }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                aria-label={ariaLabel}
                className={({ isActive }) =>
                  [styles.navLink, isActive ? styles.navLinkActive : ""].join(" ").trim()
                }
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
