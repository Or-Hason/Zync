import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { NotificationCTA } from "@/components/NotificationCTA";
import { JobMatchToast } from "@/components/JobMatchToast";
import { useNotifications } from "@/hooks/useNotifications";
import styles from "./App.module.css";

/** Root layout: persistent sidebar + data-router outlet. */
export function App(): React.JSX.Element {
  const { toast, dismissToast, navigateToAction } = useNotifications();

  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.content}>
        <NotificationCTA />
        <Outlet />
      </div>
      {toast && (
        <JobMatchToast
          jobTitle={toast.jobTitle}
          matchScore={toast.matchScore}
          jobCount={toast.jobCount}
          actionLabel={toast.actionLabel || undefined}
          onAction={navigateToAction}
          onDismiss={dismissToast}
          duration={toast.duration}
        />
      )}
    </div>
  );
}
