import { useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type Column,
  type Row,
} from "@tanstack/react-table";
import { en } from "@/i18n/en";
import type { JobListItem } from "@/types/job";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;

/** Status sort order: advanced stages first, rejections last. */
const STATUS_ORDER: Record<string, number> = {
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
const DATE_GROUPS = [
  { label: t.dateGroupToday, maxDays: 1 },
  { label: t.dateGroupLastWeek, maxDays: 7 },
  { label: t.dateGroupLastMonth, maxDays: 30 },
  { label: t.dateGroupLastYear, maxDays: 365 },
  { label: t.dateGroupOlder, maxDays: Infinity },
] as const;

function getDateGroup(createdAt: string, now: number): string {
  const diffDays = (now - new Date(createdAt).getTime()) / 86_400_000;
  for (const g of DATE_GROUPS) {
    if (diffDays < g.maxDays) return g.label;
  }
  return t.dateGroupOlder;
}

/** Status category → CSS class for coloured badge. */
function statusClass(status: string): string {
  if (status === "accepted") return styles.badgeGreen;
  if (status === "not_applied") return styles.badgeYellow;
  if (status.endsWith("_rejected") || status === "auto_rejected") return styles.badgeRed;
  return styles.badgeBlue;
}

/** Columns that stay left-aligned (all others are centered). */
function isLeftAligned(colId: string): boolean {
  return colId === "job_title" || colId === "scored_resume_ids";
}

const ONE_DAY_MS = 86_400_000;
const columnHelper = createColumnHelper<JobListItem>();

type RowEntry =
  | { kind: "sep"; label: string }
  | { kind: "data"; row: Row<JobListItem> };

function readViewedJobs(): Set<string> {
  try {
    const raw = sessionStorage.getItem("zync_viewed_jobs");
    return new Set<string>(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set<string>();
  }
}

interface Props {
  jobs: JobListItem[];
  resumeMap: Map<string, string>;
  sorting: SortingState;
  onSortingChange: React.Dispatch<React.SetStateAction<SortingState>>;
  targetRole?: string;
}

export function JobTable({ jobs, resumeMap, sorting, onSortingChange, targetRole }: Props): React.JSX.Element {
  const navigate = useNavigate();

  /**
   * Track which row IDs have already been animated.
   * Seeded from sessionStorage so navigating back doesn't re-animate viewed jobs.
   */
  const animatedRef = useRef<Set<string>>(readViewedJobs());

  const columns = useMemo(() => [
    columnHelper.accessor("job_title", {
      header: t.columnRole,
      sortingFn: (rowA, rowB) => {
        const a = (rowA.original.job_title ?? "").toLowerCase().trim();
        const b = (rowB.original.job_title ?? "").toLowerCase().trim();
        const target = targetRole?.toLowerCase().trim() ?? "";
        if (target) {
          if (a === target && b !== target) return -1;
          if (a !== target && b === target) return 1;
        }
        return a < b ? -1 : a > b ? 1 : 0;
      },
      cell: (info) => (
        <span className={styles.roleCellWrap}>
          {info.row.original.is_unread && (
            <span className={styles.unreadDot} aria-label="Unread" title="Unread" />
          )}
          {info.getValue() ?? "—"}
        </span>
      ),
    }),
    columnHelper.accessor("company_name", {
      header: t.columnCompany,
      cell: (info) => info.getValue() ?? "—",
    }),
    columnHelper.accessor("status", {
      header: t.columnStatus,
      sortingFn: (rowA, rowB) =>
        (STATUS_ORDER[rowA.original.status] ?? 999) - (STATUS_ORDER[rowB.original.status] ?? 999),
      cell: (info) => {
        const s = info.getValue();
        return (
          <span className={`${styles.badge} ${statusClass(s)}`}>
            {t.statusLabels[s] ?? s}
          </span>
        );
      },
    }),
    columnHelper.accessor("match_score", {
      header: t.columnScore,
      cell: (info) => {
        const v = info.getValue();
        return v !== null
          ? <span className={styles.score}>{v}%</span>
          : <span className={styles.dim}>—</span>;
      },
    }),
    columnHelper.accessor("created_at", {
      header: t.columnDate,
      cell: (info) =>
        new Date(info.getValue()).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        }),
    }),
    columnHelper.accessor("source_type", {
      header: t.columnSource,
      cell: (info) =>
        info.getValue() === "manual"
          ? <span className={styles.tagManual}>{t.sourceManual}</span>
          : <span className={styles.tagAuto}>{t.sourceAuto}</span>,
    }),
    columnHelper.accessor("scored_resume_ids", {
      header: t.columnCv,
      enableSorting: false,
      cell: (info) => {
        const ids = info.getValue();
        const names = ids.map((id) => resumeMap.get(id)).filter(Boolean) as string[];
        if (names.length === 0) return <span className={styles.dim}>—</span>;
        if (names.length === 1) return <span className={styles.dim}>{names[0]}</span>;
        return (
          <span
            className={styles.dim}
            title={names.join("\n")}
            style={{ cursor: "help" }}
          >
            {names[0]}{" "}
            <span className={styles.cvMoreBadge}>+{names.length - 1}</span>
          </span>
        );
      },
    }),
  ], [resumeMap, targetRole]);

  const table = useReactTable({
    data: jobs,
    columns,
    state: { sorting },
    onSortingChange,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableMultiSort: true,
  });

  function handleHeaderClick(column: Column<JobListItem>, e: React.MouseEvent): void {
    if (!column.getCanSort()) return;
    column.toggleSorting(undefined, e.shiftKey);
  }

  const isPrimaryDateDesc = sorting[0]?.id === "created_at" && sorting[0]?.desc === true;

  const sortedRows = table.getRowModel().rows;

  // Inject date group separator rows when primary sort is Date Added ↓.
  const rowEntries: RowEntry[] = [];
  if (isPrimaryDateDesc) {
    const now = Date.now();
    let lastGroup = "";
    for (const row of sortedRows) {
      const group = getDateGroup(row.original.created_at, now);
      if (group !== lastGroup) {
        rowEntries.push({ kind: "sep", label: group });
        lastGroup = group;
      }
      rowEntries.push({ kind: "data", row });
    }
  } else {
    for (const row of sortedRows) {
      rowEntries.push({ kind: "data", row });
    }
  }

  const colCount = columns.length;

  if (jobs.length === 0) {
    return <p className={styles.empty}>{t.noData}</p>;
  }

  return (
    <div className={styles.wrapper} role="region" aria-label={en.pages.explorer.title}>
      <table className={styles.table}>
        <thead>
          <tr>
            {table.getFlatHeaders().map((header) => {
              const col = header.column;
              const isSorted = col.getIsSorted();
              const left = isLeftAligned(col.id);
              return (
                <th
                  key={header.id}
                  className={`${styles.th} ${left ? "" : styles.thCenter} ${col.getCanSort() ? styles.thSortable : ""}`}
                  onClick={(e): void => handleHeaderClick(col, e)}
                  aria-sort={isSorted === "asc" ? "ascending" : isSorted === "desc" ? "descending" : "none"}
                  title={col.getCanSort() ? en.pages.explorer.shiftClickTooltip : undefined}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {isSorted === "asc" && <span className={styles.sortIcon} aria-hidden>↑</span>}
                  {isSorted === "desc" && <span className={styles.sortIcon} aria-hidden>↓</span>}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rowEntries.map((entry) => {
            if (entry.kind === "sep") {
              return (
                <tr key={`sep-${entry.label}`} className={styles.dateSepRow}>
                  <td colSpan={colCount} className={styles.dateSepCell}>
                    {entry.label}
                  </td>
                </tr>
              );
            }

            const { row } = entry;
            const job = row.original;
            const isNew = Date.now() - new Date(job.created_at).getTime() < ONE_DAY_MS;
            const shouldAnimate = isNew && !animatedRef.current.has(job.id);
            if (shouldAnimate) animatedRef.current.add(job.id);

            return (
              <tr
                key={job.id}
                className={[
                  styles.row,
                  (job.is_unread && isNew) ? styles.rowUnread : "",
                  shouldAnimate ? styles.rowNew : "",
                ].filter(Boolean).join(" ")}
                onClick={(): void => { void navigate(`/jobs/${job.id}`); }}
                role="button"
                tabIndex={0}
                aria-label={`View job: ${job.job_title ?? "Unknown"} at ${job.company_name ?? "Unknown"}`}
                onKeyDown={(e): void => {
                  if (e.key === "Enter" || e.key === " ") void navigate(`/jobs/${job.id}`);
                }}
              >
                {row.getVisibleCells().map((cell) => {
                  const left = isLeftAligned(cell.column.id);
                  return (
                    <td key={cell.id} className={`${styles.td} ${left ? "" : styles.tdCenter}`}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
