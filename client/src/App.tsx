import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import styles from "./App.module.css";

/** Root layout: persistent sidebar + data-router outlet. */
export function App(): React.JSX.Element {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.content}>
        <Outlet />
      </div>
    </div>
  );
}
