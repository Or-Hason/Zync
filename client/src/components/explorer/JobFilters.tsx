import { useResumes, useActiveResume } from "@/api/resumeApi";
import { useJobFacets } from "@/api/jobsApi";
import { en } from "@/i18n/en";
import type { JobFiltersParams } from "@/types/job";
import styles from "./JobFilters.module.css";

const f = en.pages.explorer.filters;

interface Props {
  filters: JobFiltersParams;
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
export function JobFilters({ filters, search, onSearchChange, onChange, onClear }: Props): React.JSX.Element {
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();
  /*
   * Options come from the facets endpoint (every job in the DB), NOT from the
   * currently displayed rows. Deriving them from the filtered list meant that
   * choosing a Role left that Role as the only option until the box was cleared.
   */
  const { data: facets } = useJobFacets();

  /** Unique role options: active CV target role pinned first (deduped). */
  const pinnedRole = activeResume?.target_role ?? null;
  const allRoles = facets?.roles ?? [];
  const roleOptions = pinnedRole
    ? [pinnedRole, ...allRoles.filter((r) => r.toLowerCase() !== pinnedRole.toLowerCase())]
    : allRoles;

  const companyOptions = facets?.companies ?? [];

  /**
   * Close the native datalist popup after an option is picked.
   *
   * Selecting from a datalist fires `input` with `inputType`
   * "insertReplacementText" — the one signal that distinguishes a pick from
   * ordinary typing. Without blurring, the popup lingers over the page showing
   * the single option that still matches the now-complete value.
   */
  function handleAutocompletePick(e: React.InputEvent<HTMLInputElement>): void {
    if (e.nativeEvent.inputType === "insertReplacementText") {
      e.currentTarget.blur();
    }
  }

  /**
   * Select the whole value when an autocomplete regains focus.
   *
   * A `<datalist>` popup only offers options that substring-match the input's
   * current value, so once a full option is chosen it is the only suggestion
   * left. Pre-selecting the text means one keystroke replaces it and the full
   * list comes back, instead of forcing the user to clear the box by hand.
   *
   * Deferred a frame on purpose: the browser positions the caret *after* the
   * focus handler returns, so selecting synchronously here is immediately undone.
   */
  function handleAutocompleteFocus(e: React.FocusEvent<HTMLInputElement>): void {
    const input = e.currentTarget;
    requestAnimationFrame(() => input.select());
  }

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
          onInput={handleAutocompletePick}
          onFocus={handleAutocompleteFocus}
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
          onInput={handleAutocompletePick}
          onFocus={handleAutocompleteFocus}
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
