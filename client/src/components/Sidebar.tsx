import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { en } from "@/i18n/en";
import {
  AddJobIcon,
  ChevronIcon,
  DashboardIcon,
  DocumentsIcon,
  ExplorerIcon,
  SettingsIcon,
} from "./navIcons";
import styles from "./Sidebar.module.css";

interface NavItem {
  to: string;
  label: string;
  ariaLabel: string;
  icon: () => React.JSX.Element;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",          label: en.nav.dashboard,        ariaLabel: "Navigate to Dashboard",         icon: DashboardIcon },
  { to: "/explorer",  label: en.nav.explorer,         ariaLabel: "Navigate to Job Explorer",      icon: ExplorerIcon  },
  { to: "/jobs/add",  label: en.nav.addJob,           ariaLabel: "Navigate to Add Job",           icon: AddJobIcon    },
  { to: "/documents", label: en.nav.documentsManager, ariaLabel: "Navigate to Documents Manager", icon: DocumentsIcon },
  { to: "/settings",  label: en.nav.settings,         ariaLabel: "Navigate to Settings",          icon: SettingsIcon  },
];

const COLLAPSED_KEY = "zync_sidebar_collapsed";

/**
 * Persistent left-side navigation sidebar, collapsible to an icon rail.
 *
 * The collapsed state is kept in localStorage (not sessionStorage) because it is
 * a lasting layout preference rather than per-visit state — collapsing it once
 * should survive a restart.
 */
export function Sidebar(): React.JSX.Element {
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(COLLAPSED_KEY) === "true",
  );

  useEffect(() => {
    localStorage.setItem(COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  return (
    <aside
      className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ""}`}
      aria-label="Main navigation"
    >
      <div className={styles.brand}>
        {!collapsed && (
          <span className={styles.brandName} aria-label={en.app.name}>
            {en.app.name}
          </span>
        )}
        <button
          type="button"
          className={styles.collapseBtn}
          onClick={(): void => setCollapsed((c) => !c)}
          aria-label={collapsed ? en.nav.expand : en.nav.collapse}
          aria-expanded={!collapsed}
          title={collapsed ? en.nav.expand : en.nav.collapse}
        >
          <span className={collapsed ? styles.chevronFlipped : undefined}>
            <ChevronIcon />
          </span>
        </button>
      </div>

      <nav>
        <ul className={styles.navList} role="list">
          {NAV_ITEMS.map(({ to, label, ariaLabel, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === "/"}
                aria-label={ariaLabel}
                // The label is hidden when collapsed, so the tooltip is the only
                // way to identify an icon without expanding the rail.
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  [
                    styles.navLink,
                    collapsed ? styles.navLinkCollapsed : "",
                    isActive ? styles.navLinkActive : "",
                  ].join(" ").trim()
                }
              >
                <span className={styles.navIcon}>
                  <Icon />
                </span>
                <span className={styles.navLabel}>{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
