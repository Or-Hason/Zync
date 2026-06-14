import { useResumes, useActiveResume } from "@/api/resumeApi";
import { en } from "@/i18n/en";
import type { JobFiltersParams, JobListItem } from "@/types/job";
import styles from "./JobFilters.module.css";

const f = en.pages.explorer.filters;

interface Props {
  filters: JobFiltersParams;
  jobs: JobListItem[];
  search: string;
  onSearchChange: (v: string) => void;
  onChange: (patch: Partial<JobFiltersParams>) => void;
  onClear: () => void;
}

/**
 * Primary filter bar for the Job Explorer.
 *
 * Receives the debounced search value separately (`search` / `onSearchChange`)
 * so the input stays responsive while the API query waits for the debounce.
 */
export function JobFilters({ filters, jobs, search, onSearchChange, onChange, onClear }: Props): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();

  /** Unique role options: active CV target role pinned first (deduped). */
  const pinnedRole = activeResume?.target_role ?? null;
  const allRoles = Array.from(new Set(jobs.map((j) => j.job_title).filter(Boolean) as string[])).sort();
  const roleOptions = pinnedRole
    ? [pinnedRole, ...allRoles.filter((r) => r.toLowerCase() !== pinnedRole.toLowerCase())]
    : allRoles;

  /** Unique company suggestions derived from current job list. */
  const companyOptions = Array.from(
    new Set(jobs.map((j) => j.company_name).filter(Boolean) as string[])
  ).sort();

  const hasActiveFilters =
    !!filters.date_from ||
    !!filters.date_to ||
    filters.min_score !== undefined ||
    !!filters.role ||
    !!filters.company ||
    !!filters.cv_id ||
    !!search;

  return (
    <div className={styles.bar} role="search" aria-label="Primary job filters">
      {/* Free Search */}
      <div className={`${styles.field} ${styles.fieldSearch}`}>
        <span className={styles.miniLabel}>{f.freeSearchLabel}</span>
        <input
          type="search"
          className={styles.search}
          placeholder={f.search}
          value={search}
          onChange={(e): void => onSearchChange(e.target.value)}
          aria-label={f.freeSearchLabel}
        />
      </div>

      {/* Date Range */}
      <div className={styles.field}>
        <span className={styles.miniLabel}>{f.dateRangeLabel}</span>
        <div className={styles.dateRange}>
          <input
            type="date"
            className={styles.dateInput}
            value={filters.date_from ?? ""}
            onChange={(e): void => onChange({ date_from: e.target.value || undefined })}
            aria-label={f.dateFrom}
            title={f.dateFrom}
          />
          <span className={styles.dateSep}>–</span>
          <input
            type="date"
            className={styles.dateInput}
            value={filters.date_to ?? ""}
            onChange={(e): void => onChange({ date_to: e.target.value || undefined })}
            aria-label={f.dateTo}
            title={f.dateTo}
          />
        </div>
      </div>

      {/* Min Score */}
      <div className={styles.field}>
        <label className={styles.miniLabel} htmlFor="minScore">{f.minScoreLabel}</label>
        <input
          id="minScore"
          type="number"
          className={styles.numberInput}
          min={0}
          max={100}
          value={filters.min_score ?? ""}
          placeholder="0"
          onChange={(e): void =>
            onChange({ min_score: e.target.value ? Number(e.target.value) : undefined })
          }
          aria-label={f.minScoreLabel}
        />
      </div>

      {/* Role (with active CV target role pinned at top) */}
      <div className={styles.field}>
        <label className={styles.miniLabel}>{f.roleLabel}</label>
        <input
          type="text"
          className={styles.autocomplete}
          placeholder={f.rolePlaceholder}
          list="role-options"
          value={filters.role ?? ""}
          onChange={(e): void => onChange({ role: e.target.value || undefined })}
          aria-label={f.roleLabel}
        />
        <datalist id="role-options">
          {pinnedRole && <option value={pinnedRole} />}
          {roleOptions
            .filter((r) => !pinnedRole || r.toLowerCase() !== pinnedRole.toLowerCase())
            .map((r) => <option key={r} value={r} />)}
        </datalist>
      </div>

      {/* Company */}
      <div className={styles.field}>
        <label className={styles.miniLabel}>{f.companyLabel}</label>
        <input
          type="text"
          className={styles.autocomplete}
          placeholder={f.companyPlaceholder}
          list="company-options"
          value={filters.company ?? ""}
          onChange={(e): void => onChange({ company: e.target.value || undefined })}
          aria-label={f.companyLabel}
        />
        <datalist id="company-options">
          {companyOptions.map((c) => <option key={c} value={c} />)}
        </datalist>
      </div>

      {/* CV Used */}
      <div className={styles.field}>
        <span className={styles.miniLabel}>{f.cvUsedLabel}</span>
        <select
          className={styles.select}
          value={filters.cv_id ?? ""}
          onChange={(e): void => onChange({ cv_id: e.target.value || undefined })}
          aria-label={f.cvUsedLabel}
        >
          <option value="">{f.cvUsedAll}</option>
          {resumes.map((r) => (
            <option key={r.id} value={r.id}>{r.version_name}</option>
          ))}
        </select>
      </div>

      {/* Clear button */}
      {hasActiveFilters && (
        <button type="button" className={styles.clearBtn} onClick={onClear} aria-label={f.clearAll}>
          {f.clearAll}
        </button>
      )}
    </div>
  );
}
