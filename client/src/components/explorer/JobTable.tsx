import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type Column,
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

/** Status category → CSS class for coloured badge. */
function statusClass(status: string): string {
  if (status === "accepted") return styles.badgeGreen;
  if (status === "not_applied") return styles.badgeYellow;
  if (status.endsWith("_rejected") || status === "auto_rejected") return styles.badgeRed;
  return styles.badgeBlue;
}

const ONE_DAY_MS = 86_400_000;

const columnHelper = createColumnHelper<JobListItem>();

interface Props {
  jobs: JobListItem[];
  resumeMap: Map<string, string>;
  sorting: SortingState;
  onSortingChange: React.Dispatch<React.SetStateAction<SortingState>>;
}

export function JobTable({ jobs, resumeMap, sorting, onSortingChange }: Props): React.JSX.Element {
  const navigate = useNavigate();
  /** Track which row IDs have already been animated so refresh doesn't re-fire. */
  const animatedRef = useRef<Set<string>>(new Set());

  const columns = [
    columnHelper.accessor("job_title", {
      header: t.columnRole,
      cell: (info) => info.getValue() ?? "—",
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
        return v !== null ? <span className={styles.score}>{v}%</span> : <span className={styles.dim}>—</span>;
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
        info.getValue() === "manual" ? (
          <span className={styles.tagManual}>{t.sourceManual}</span>
        ) : (
          <span className={styles.tagAuto}>{t.sourceAuto}</span>
        ),
    }),
    columnHelper.accessor("scored_by_resume_id", {
      header: t.columnCv,
      enableSorting: false,
      cell: (info) => {
        const id = info.getValue();
        return <span className={styles.dim}>{id ? (resumeMap.get(id) ?? "—") : "—"}</span>;
      },
    }),
  ];

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
              return (
                <th
                  key={header.id}
                  className={`${styles.th} ${col.getCanSort() ? styles.thSortable : ""}`}
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
          {table.getRowModel().rows.map((row) => {
            const job = row.original;
            const isNew = Date.now() - new Date(job.created_at).getTime() < ONE_DAY_MS;
            const shouldAnimate = isNew && !animatedRef.current.has(job.id);
            if (shouldAnimate) animatedRef.current.add(job.id);

            return (
              <tr
                key={job.id}
                className={`${styles.row} ${shouldAnimate ? styles.rowNew : ""}`}
                onClick={(): void => { void navigate(`/jobs/${job.id}`); }}
                role="button"
                tabIndex={0}
                aria-label={`View job: ${job.job_title ?? "Unknown"} at ${job.company_name ?? "Unknown"}`}
                onKeyDown={(e): void => {
                  if (e.key === "Enter" || e.key === " ") void navigate(`/jobs/${job.id}`);
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className={styles.td}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
