/** Central English string dictionary — all UI text must reference this. Never hardcode strings in JSX. */

import { app, nav, common, notifications } from "./locales/en/core";
import { dashboard } from "./locales/en/dashboard";
import { resumeManager } from "./locales/en/resumeManager";
import { settings } from "./locales/en/settings";
import { jobAdd } from "./locales/en/jobAdd";
import { documentsManager } from "./locales/en/documentsManager";
import { jobDetail } from "./locales/en/jobDetail";
import { coverLetter } from "./locales/en/coverLetter";
import { explorer } from "./locales/en/explorer";

export const en = {
  app,
  nav,
  pages: {
    dashboard,
    resumeManager,
    settings,
    jobAdd,
    documentsManager,
    jobDetail,
    coverLetter,
    explorer,
  },
  notifications,
  common,
} as const;

export type Dictionary = typeof en;
