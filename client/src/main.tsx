import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { DashboardPage } from "./pages/DashboardPage";
import { JobAddPage } from "./pages/JobAddPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { ResumeManagerPage } from "./pages/ResumeManagerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { en } from "./i18n/en";
import "./styles/globals.css";

// Drive document title from i18n so it is never hardcoded in HTML.
document.title = en.app.name;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element #root not found");

const router = createBrowserRouter([
  {
    element: <App />,
    children: [
      { path: "/",           element: <DashboardPage /> },
      { path: "/jobs/add",   element: <JobAddPage /> },
      { path: "/jobs/:id",   element: <JobDetailPage /> },
      { path: "/resumes",    element: <ResumeManagerPage /> },
      { path: "/settings",   element: <SettingsPage /> },
    ],
  },
]);

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
