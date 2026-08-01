import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type SortingState,
  type Column,
  type Row,
} from "@tanstack/react-table";
import { en } from "@/i18n/en";
import type { JobListItem } from "@/types/job";
import { useJobTableColumns } from "./useJobTableColumns";
import { getDateGroup, isLeftAligned, ONE_DAY_MS, readViewedJobs } from "./jobTableHelpers";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;

type RowEntry =
  | { kind: "sep"; label: string }
  | { kind: "data"; row: Row<JobListItem> };

interface Props {
  jobs: JobListItem[];
  sorting: SortingState;
  onSortingChange: React.Dispatch<React.SetStateAction<SortingState>>;
  targetRole?: string;
  /** The user's Active Resume; drives which CV the CV/Score columns surface. */
  activeResumeId: string | null;
  /** When true, ignore the Active Resume and always show the top-scoring CV. */
  showBestMatch: boolean;
}

/**
 * The Explorer data grid.
 *
 * `CV Used` and `Score` are derived columns: both read the same
 * `selectPrimaryScore` result, so the score shown always belongs to the CV named
 * beside it. Changing the Active Resume re-runs that selection (it is a column
 * dependency), which is what re-renders the grid without a refetch.
 */
export function JobTable({
  jobs,
  sorting,
  onSortingChange,
  targetRole,
  activeResumeId,
  showBestMatch,
}: Props): React.JSX.Element {
  const navigate = useNavigate();

  /**
   * Track which row IDs have already been animated.
   * Seeded from sessionStorage so navigating back doesn't re-animate viewed jobs.
   */
  const animatedRef = useRef<Set<string>>(readViewedJobs());

  const columns = useJobTableColumns({ targetRole, activeResumeId, showBestMatch });

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
