import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { DashboardPage } from "./pages/DashboardPage";
import { JobExplorerPage } from "./pages/JobExplorerPage";
import { JobAddPage } from "./pages/JobAddPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { DocumentsManagerPage } from "./pages/DocumentsManagerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { Navigate } from "react-router-dom";
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
      { path: "/",            element: <DashboardPage /> },
      { path: "/explorer",    element: <JobExplorerPage /> },
      { path: "/jobs/add",    element: <JobAddPage /> },
      { path: "/jobs/:id",    element: <JobDetailPage /> },
      { path: "/documents",   element: <DocumentsManagerPage /> },
      { path: "/resumes",     element: <Navigate to="/documents" replace /> },
      { path: "/settings",    element: <SettingsPage /> },
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
