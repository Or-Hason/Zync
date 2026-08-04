import { useMemo } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { en } from "@/i18n/en";
import type { JobRow } from "@/types/job";
import { buildScoreTooltip } from "./scoreSelection";
import { CvUsedHeader } from "./CvUsedHeader";
import { STATUS_ORDER, statusClass } from "./jobTableHelpers";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;
const columnHelper = createColumnHelper<JobRow>();

interface UseJobTableColumnsParams {
  targetRole?: string;
  /** The user's Active Resume — used only to badge the CV as "Active". */
  activeResumeId: string | null;
  /** Current CV mode, rendered as a control inside the CV Used header. */
  showBestMatch: boolean;
  onShowBestMatchChange: (value: boolean) => void;
}

/**
 * Builds the Explorer grid's column definitions.
 *
 * `CV Used` and `Score` both read `row.primaryScore`, resolved once per job in
 * `JobTable`'s `data` memo, so the score shown always belongs to the CV named
 * beside it. They must NOT resolve it themselves — see the note in `JobTable`
 * on TanStack's accessor value cache.
 *
 * `size` is a ratio, not a pixel width: the table is `table-layout: fixed`, so
 * the browser scales these to fill the container. Fixed layout is what makes a
 * long CV name clip inside its cell instead of stretching the table past the
 * scroll container's right edge.
 */
export function useJobTableColumns({
  targetRole,
  activeResumeId,
  showBestMatch,
  onShowBestMatchChange,
}: UseJobTableColumnsParams) {
  return useMemo(() => [
    columnHelper.accessor("job_title", {
      header: t.columnRole,
      size: 210,
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
      size: 130,
      cell: (info) => info.getValue() ?? "—",
    }),
    columnHelper.accessor("status", {
      header: t.columnStatus,
      size: 135,
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
    columnHelper.accessor((row) => row.primaryScore?.match_score ?? null, {
      id: "match_score",
      header: t.columnScore,
      size: 80,
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
    }),
    columnHelper.accessor("created_at", {
      header: t.columnDate,
      size: 105,
      cell: (info) =>
        new Date(info.getValue()).toLocaleDateString(undefined, {
          year: "numeric",
          month: "short",
          day: "numeric",
        }),
    }),
    columnHelper.accessor("source_type", {
      header: t.columnSource,
      size: 85,
      cell: (info) =>
        info.getValue() === "manual"
          ? <span className={styles.tagManual}>{t.sourceManual}</span>
          : <span className={styles.tagAuto}>{t.sourceAuto}</span>,
    }),
    columnHelper.display({
      id: "cv_used",
      header: () => (
        <CvUsedHeader showBestMatch={showBestMatch} onChange={onShowBestMatchChange} />
      ),
      size: 205,
      cell: ({ row }) => {
        const { scores, primaryScore: primary } = row.original;
        if (primary === null) return <span className={styles.dim}>—</span>;

        const isActive = primary.resume_id === activeResumeId;
        const others = scores.length - 1;
        // Always tooltipped: the name is truncated to fit the column, so hover
        // is the only way to read a long CV name even when it is the only one.
        const tooltip = others > 0
          ? buildScoreTooltip(scores, activeResumeId, t.cvActiveBadge)
          : primary.resume_name ?? undefined;

        return (
          <span
            className={styles.cvCellWrap}
            title={tooltip}
            style={{ cursor: "help" }}
          >
            <span className={`${styles.dim} ${styles.cvName}`}>
              {primary.resume_name ?? "—"}
            </span>
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
  ], [activeResumeId, targetRole, showBestMatch, onShowBestMatchChange]);
}
