import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { NotificationCTA } from "@/components/NotificationCTA";
import { useNotifications } from "@/hooks/useNotifications";
import styles from "./App.module.css";

/** Root layout: persistent sidebar + data-router outlet. */
export function App(): React.JSX.Element {
  useNotifications();

  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.content}>
        <NotificationCTA />
        <Outlet />
      </div>
    </div>
  );
}
