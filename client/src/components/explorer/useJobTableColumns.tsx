import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { en } from "@/i18n/en";
import type { JobListItem } from "@/types/job";
import { buildScoreTooltip, selectPrimaryScore } from "./scoreSelection";
import { STATUS_ORDER, statusClass } from "./jobTableHelpers";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;
const columnHelper = createColumnHelper<JobListItem>();

interface UseJobTableColumnsParams {
  targetRole?: string;
  /** The user's Active Resume; drives which CV the CV/Score columns surface. */
  activeResumeId: string | null;
  /** When true, ignore the Active Resume and always show the top-scoring CV. */
  showBestMatch: boolean;
}

/**
 * Builds the Explorer grid's column definitions.
 *
 * `CV Used` and `Score` are derived columns: both read the same
 * `selectPrimaryScore` result, so the score shown always belongs to the CV named
 * beside it. Changing the Active Resume re-runs that selection (it is a column
 * dependency), which is what re-renders the grid without a refetch.
 */
export function useJobTableColumns({
  targetRole,
  activeResumeId,
  showBestMatch,
}: UseJobTableColumnsParams) {
  return useMemo(() => [
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
    // Derived, not stored: the score of whichever CV the CV Used column shows.
    columnHelper.accessor(
      (row) => selectPrimaryScore(row.scores, activeResumeId, showBestMatch)?.match_score ?? null,
      {
        id: "match_score",
        header: t.columnScore,
        // Unscored jobs sort as -1 so they sink to the bottom on the default
        // (descending) score sort rather than landing between real scores.
        sortingFn: (rowA, rowB, colId) =>
          ((rowA.getValue(colId) as number | null) ?? -1) -
          ((rowB.getValue(colId) as number | null) ?? -1),
        cell: (info) => {
          const v = info.getValue();
          return v !== null
            ? <span className={styles.score}>{v}%</span>
            : <span className={styles.dim}>—</span>;
        },
      },
    ),
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
    columnHelper.display({
      id: "cv_used",
      header: t.columnCv,
      cell: ({ row }) => {
        const { scores } = row.original;
        const primary = selectPrimaryScore(scores, activeResumeId, showBestMatch);
        if (primary === null) return <span className={styles.dim}>—</span>;

        const isActive = primary.resume_id === activeResumeId;
        const others = scores.length - 1;
        const tooltip = others > 0
          ? buildScoreTooltip(scores, activeResumeId, t.cvActiveBadge)
          : undefined;

        return (
          <span
            className={styles.cvCellWrap}
            title={tooltip}
            style={others > 0 ? { cursor: "help" } : undefined}
          >
            <span className={styles.dim}>{primary.resume_name ?? "—"}</span>
            {isActive && (
              <span className={styles.cvActiveBadge} title={t.cvActiveTooltip}>
                {t.cvActiveBadge}
              </span>
            )}
            {others > 0 && (
              <span
                className={styles.cvMoreBadge}
                aria-label={`${others} ${t.cvOtherScoresAriaLabel}`}
              >
                +{others}
              </span>
            )}
          </span>
        );
      },
    }),
  ], [activeResumeId, showBestMatch, targetRole]);
}
