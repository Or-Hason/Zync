import { en } from "@/i18n/en";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;

/** Status sort order: advanced stages first, rejections last. */
export const STATUS_ORDER: Record<string, number> = {
  accepted: 0,
  hr_interview: 1,
  professional_interview: 2,
  home_test: 3,
  assessment_task: 4,
  applied: 5,
  not_applied: 6,
  auto_rejected: 7,
  hr_interview_rejected: 8,
  professional_interview_rejected: 9,
  home_test_rejected: 10,
  assessment_rejected: 11,
  user_rejected: 12,
};

/** Date group thresholds (ascending days from now). */
export const DATE_GROUPS = [
  { label: t.dateGroupToday, maxDays: 1 },
  { label: t.dateGroupLastWeek, maxDays: 7 },
  { label: t.dateGroupLastMonth, maxDays: 30 },
  { label: t.dateGroupLastYear, maxDays: 365 },
  { label: t.dateGroupOlder, maxDays: Infinity },
] as const;

export function getDateGroup(createdAt: string, now: number): string {
  const diffDays = (now - new Date(createdAt).getTime()) / 86_400_000;
  for (const g of DATE_GROUPS) {
    if (diffDays < g.maxDays) return g.label;
  }
  return t.dateGroupOlder;
}

/** Status category → CSS class for coloured badge. */
export function statusClass(status: string): string {
  if (status === "accepted") return styles.badgeGreen;
  if (status === "not_applied") return styles.badgeYellow;
  if (status.endsWith("_rejected") || status === "auto_rejected") return styles.badgeRed;
  return styles.badgeBlue;
}

/** Columns that stay left-aligned (all others are centered). */
export function isLeftAligned(colId: string): boolean {
  return colId === "job_title" || colId === "cv_used";
}

export const ONE_DAY_MS = 86_400_000;

export function readViewedJobs(): Set<string> {
  try {
    const raw = sessionStorage.getItem("zync_viewed_jobs");
    return new Set<string>(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set<string>();
  }
}
