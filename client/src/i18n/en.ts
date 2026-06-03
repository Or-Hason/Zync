/** Central English string dictionary — all UI text must reference this. Never hardcode strings in JSX. */
export const en = {
  app: {
    name: "Zync",
    tagline: "AI-driven job hunting",
    description: "Zync — AI-driven job hunting and application manager",
  },
  nav: {
    dashboard: "Dashboard",
    resumeManager: "Resume Manager",
    settings: "Settings",
  },
  pages: {
    dashboard: {
      title: "Dashboard",
      subtitle: "Your job search at a glance",
    },
    resumeManager: {
      title: "Resume Manager",
      subtitle: "Upload, parse, and manage your resumes",
    },
    settings: {
      title: "Settings",
      subtitle: "Configure your Zync preferences",
    },
  },
  common: {
    loading: "Loading…",
    error: "Something went wrong",
    save: "Save Changes",
    cancel: "Cancel",
    add: "Add",
    remove: "Remove",
    edit: "Edit",
    upload: "Upload",
    comingSoon: "Coming soon",
  },
} as const;

export type Dictionary = typeof en;
