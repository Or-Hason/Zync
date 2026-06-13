import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type SortingState } from "@tanstack/react-table";
import { en } from "@/i18n/en";
import { useJobs, useJobSkills } from "@/api/jobsApi";
import { useResumes } from "@/api/resumeApi";
import type { JobFiltersParams } from "@/types/job";
import { JobTable } from "@/components/explorer/JobTable";
import { JobFilters } from "@/components/explorer/JobFilters";
import { SecondaryFilters } from "@/components/explorer/SecondaryFilters";
import { ScanNowButton } from "@/components/jobs/ScanNowButton";
import { ActiveResumeSelector } from "@/components/jobs/ActiveResumeSelector";
import pageStyles from "./Page.module.css";
import styles from "./JobExplorerPage.module.css";

const s = en.pages.explorer;
const SEARCH_DEBOUNCE_MS = 300;
const EMPTY_FILTERS: JobFiltersParams = {};
const FILTER_SESSION_KEY = "zync_explorer_filters";

function loadSavedState(): { filters: JobFiltersParams; search: string } {
  try {
    const raw = sessionStorage.getItem(FILTER_SESSION_KEY);
    if (raw) return JSON.parse(raw) as { filters: JobFiltersParams; search: string };
  } catch { /* ignore malformed data */ }
  return { filters: EMPTY_FILTERS, search: "" };
}

export function JobExplorerPage(): React.JSX.Element {
  const qc = useQueryClient();
  const saved = useMemo(loadSavedState, []);

  const [filters, setFilters] = useState<JobFiltersParams>(saved.filters);
  const [searchInput, setSearchInput] = useState(saved.search);
  const [debouncedSearch, setDebouncedSearch] = useState(saved.search);
  const [sorting, setSorting] = useState<SortingState>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Debounce free-text search so the API is not hit on every keystroke. */
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(searchInput), SEARCH_DEBOUNCE_MS);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchInput]);

  /** Persist filter state across navigation within the same session. */
  useEffect(() => {
    sessionStorage.setItem(FILTER_SESSION_KEY, JSON.stringify({ filters, search: searchInput }));
  }, [filters, searchInput]);

  const activeFilters: JobFiltersParams = useMemo(
    () => ({ ...filters, q: debouncedSearch || undefined }),
    [filters, debouncedSearch],
  );

  const { data: jobs = [], isLoading, isFetching } = useJobs(activeFilters);
  const { data: allSkills = [] } = useJobSkills();
  const { data: resumes = [] } = useResumes();

  const resumeMap = useMemo(
    () => new Map(resumes.map((r) => [r.id, r.version_name])),
    [resumes],
  );

  const handleFilterChange = useCallback((patch: Partial<JobFiltersParams>): void => {
    setFilters((prev) => ({ ...prev, ...patch }));
  }, []);

  function handleClearFilters(): void {
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setDebouncedSearch("");
  }

  function handleRefresh(): void {
    void qc.invalidateQueries({ queryKey: ["jobs", "list"] });
  }

  return (
    <main className={pageStyles.page}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={pageStyles.pageTitle}>{s.title}</h1>
          <p className={pageStyles.pageSubtitle}>{s.subtitle}</p>
        </div>
        <div className={styles.headerRight}>
          <ActiveResumeSelector />
          <ScanNowButton />
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={handleRefresh}
            aria-label={isFetching ? s.refreshing : s.refresh}
            disabled={isFetching}
          >
            <span className={isFetching ? styles.spinIcon : undefined} aria-hidden>↺</span>
            {isFetching ? s.refreshing : s.refresh}
          </button>
        </div>
      </header>

      <JobFilters
        filters={filters}
        jobs={jobs}
        search={searchInput}
        onSearchChange={setSearchInput}
        onChange={handleFilterChange}
        onClear={handleClearFilters}
      />

      <SecondaryFilters
        filters={filters}
        allSkills={allSkills}
        onChange={handleFilterChange}
      />

      {isLoading ? (
        <p className={styles.loading} aria-live="polite">{s.loading}</p>
      ) : (
        <JobTable
          jobs={jobs}
          resumeMap={resumeMap}
          sorting={sorting}
          onSortingChange={setSorting}
        />
      )}
    </main>
  );
}
