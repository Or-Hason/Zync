export const app = {
  name: "Zync",
  tagline: "AI-driven job hunting",
  description: "Zync — AI-driven job hunting and application manager",
} as const;

export const nav = {
  dashboard: "Dashboard",
  explorer: "Job Explorer",
  addJob: "Add Job",
  documentsManager: "Documents Manager",
  settings: "Settings",
} as const;

export const notifications = {
  title: "New Job Match",
  titleMultiple: "New Jobs Found",
  /** Template — substitute {jobTitle} and {score} at call site. */
  body: "{jobTitle} — Score: {score}",
  bodyMultiple: "Found {count} new jobs matching your profile.",
  /** In-app toast shown on the Explorer page (persistent until dismissed). */
  toastExplorer: "New match: {jobTitle} (Score: {score})",
  toastExplorerMultiple: "{count} new matches found!",
  /** In-app toast shown on non-Explorer pages with navigation action. */
  viewMatches: "View matches",
  viewJob: "View job",
  ctaBanner: "Enable notifications to get background alerts.",
  enableBtn: "Enable",
  dontAskAgain: "Don't ask me again",
  dismiss: "Dismiss",
} as const;

export const common = {
  loading: "Loading…",
  error: "Something went wrong",
  save: "Save Changes",
  cancel: "Cancel",
  add: "Add",
  remove: "Remove",
  edit: "Edit",
  upload: "Upload",
  comingSoon: "Coming soon",
} as const;
