import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type SortingState } from "@tanstack/react-table";
import { useSearchParams } from "react-router-dom";
import { en } from "@/i18n/en";
import { useJobs, useJobSkills, useMarkAllJobsRead } from "@/api/jobsApi";
import { useActiveResume } from "@/api/resumeApi";
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
const BEST_MATCH_SESSION_KEY = "zync_explorer_best_match";

function loadSavedState(): { filters: JobFiltersParams; search: string } {
  try {
    const raw = sessionStorage.getItem(FILTER_SESSION_KEY);
    if (raw) return JSON.parse(raw) as { filters: JobFiltersParams; search: string };
  } catch { /* ignore malformed data */ }
  return { filters: EMPTY_FILTERS, search: "" };
}

export function JobExplorerPage(): React.JSX.Element {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const saved = useMemo(loadSavedState, []);

  const [filters, setFilters] = useState<JobFiltersParams>(saved.filters);
  const [searchInput, setSearchInput] = useState(saved.search);
  const [debouncedSearch, setDebouncedSearch] = useState(saved.search);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [showBestMatch, setShowBestMatch] = useState<boolean>(
    () => sessionStorage.getItem(BEST_MATCH_SESSION_KEY) === "true",
  );
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** Detect URL filter parameters (e.g., from clicking job match notification action) and refresh table. */
  useEffect(() => {
    const isNewParam = searchParams.get("is_new") === "true";
    const isUnreadParam = searchParams.get("is_unread") === "true";
    if (isNewParam || isUnreadParam) {
      console.log("[JobExplorerPage] Notification action filter params detected in URL -> applying filters & refreshing table");
      setFilters((prev) => ({
        ...prev,
        is_new: isNewParam ? true : prev.is_new,
        is_unread: isUnreadParam ? true : prev.is_unread,
      }));
      void qc.invalidateQueries({ queryKey: ["jobs", "list"] });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, qc]);

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

  /** Persist the Best Match override so it survives navigation. */
  useEffect(() => {
    sessionStorage.setItem(BEST_MATCH_SESSION_KEY, String(showBestMatch));
  }, [showBestMatch]);

  const activeFilters: JobFiltersParams = useMemo(
    () => ({ ...filters, q: debouncedSearch || undefined }),
    [filters, debouncedSearch],
  );

  const { data: jobs = [], isLoading, isFetching } = useJobs(activeFilters);
  const { mutate: markAllRead, isPending: isMarkingAllRead } = useMarkAllJobsRead();
  const { data: allSkills = [] } = useJobSkills();
  const { data: activeResume } = useActiveResume();

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
          {/*
            Best Match override. OFF (default) = Active Resume priority;
            ON = always surface the highest-scoring CV per job.
          */}
          <label className={styles.toggle} title={s.showBestMatchTooltip}>
            <input
              type="checkbox"
              className={styles.toggleInput}
              checked={showBestMatch}
              onChange={(e): void => setShowBestMatch(e.target.checked)}
              aria-label={s.showBestMatch}
            />
            <span className={styles.toggleTrack} aria-hidden>
              <span className={styles.toggleThumb} />
            </span>
            <span className={styles.toggleLabel}>{s.showBestMatch}</span>
          </label>
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
          <button
            type="button"
            className={styles.refreshBtn}
            onClick={(): void => {
              if (window.confirm(s.markAllReadConfirm)) markAllRead();
            }}
            aria-label={s.markAllRead}
            disabled={isMarkingAllRead}
          >
            {s.markAllRead}
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
          sorting={sorting}
          onSortingChange={setSorting}
          targetRole={activeResume?.target_role ?? undefined}
          // Passing the ID (not the object) is what makes the grid re-render
          // with the new CV/Score priority the moment the active CV changes.
          activeResumeId={activeResume?.id ?? null}
          showBestMatch={showBestMatch}
        />
      )}
    </main>
  );
}
