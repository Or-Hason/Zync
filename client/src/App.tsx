import { Route, Routes } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { DashboardPage } from "@/pages/DashboardPage";
import { ResumeManagerPage } from "@/pages/ResumeManagerPage";
import { SettingsPage } from "@/pages/SettingsPage";
import styles from "./App.module.css";

/** Root layout: persistent sidebar + routed content area. */
export function App(): React.JSX.Element {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.content}>
        <Routes>
          <Route path="/"         element={<DashboardPage />} />
          <Route path="/resumes"  element={<ResumeManagerPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
