/**
 * Inline nav icons for the collapsed sidebar.
 *
 * Hand-rolled SVG rather than an icon package: five glyphs do not justify a new
 * dependency, and inlining keeps them themable via `currentColor`.
 */

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

/** Dashboard — four panels. */
export function DashboardIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS}>
      <rect x="3" y="3" width="7" height="8" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="11" width="7" height="10" rx="1.5" />
    </svg>
  );
}

/** Job Explorer — magnifying glass over a list. */
export function ExplorerIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4.5 4.5" />
    </svg>
  );
}

/** Add Job — plus in a rounded square. */
export function AddJobIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS}>
      <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
      <path d="M12 8.5v7M8.5 12h7" />
    </svg>
  );
}

/** Documents Manager — stacked pages. */
export function DocumentsIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS}>
      <path d="M8 3.5h6.5L19 8v9.5A1.5 1.5 0 0 1 17.5 19H8a1.5 1.5 0 0 1-1.5-1.5V5A1.5 1.5 0 0 1 8 3.5Z" />
      <path d="M14 3.5V8h4.5" />
      <path d="M4.5 7v12A1.5 1.5 0 0 0 6 20.5h9" />
    </svg>
  );
}

/** Settings — sliders. */
export function SettingsIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS}>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2.2" />
      <circle cx="8" cy="17" r="2.2" />
    </svg>
  );
}

/** Chevron used by the collapse/expand control. */
export function ChevronIcon(): React.JSX.Element {
  return (
    <svg {...ICON_PROPS} width={16} height={16}>
      <path d="M15 5l-7 7 7 7" />
    </svg>
  );
}
