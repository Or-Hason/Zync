import { useState, useEffect } from "react";
import { Link, useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useJob, useMarkJobRead, useScrapeJob } from "@/api/jobsApi";
import { useActiveResume } from "@/api/resumeApi";
import type { JobScrapeResponse } from "@/types/job";
import { JobCard } from "@/components/jobs/JobCard";
import { ActiveResumeSelector } from "@/components/jobs/ActiveResumeSelector";
import { en } from "@/i18n/en";
import pageStyles from "./Page.module.css";
import detailStyles from "./JobDetailPage.module.css";

const s = en.pages.jobDetail;

/**
 * Deep-link destination for job-match notifications.
 *
 * Loads the job from the React Query cache when available (staleTime 5 min),
 * falling back to GET /api/jobs/:id. Renders the existing JobCard so the full
 * scoring breakdown is visible without re-running the pipeline. Supports
 * in-page rescoring when the active resume differs from the scored one.
 */
export function JobDetailPage(): React.JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: job, isLoading, isError } = useJob(id ?? null);
  const { data: activeResume } = useActiveResume();
  const { mutate: markRead } = useMarkJobRead();
  const { mutate: requestScore, isPending: isScoringPending } = useScrapeJob();
  const [searchParams, setSearchParams] = useSearchParams();
  const shouldRescore = searchParams.get("rescore") === "1";
  const [localResult, setLocalResult] = useState<JobScrapeResponse | null>(null);

  useEffect(() => {
    if (!shouldRescore || !job?.id) return;
    setSearchParams({}, { replace: true });
    requestScore(
      { existing_job_id: job.id },
      { onSuccess: (result) => setLocalResult(result) },
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldRescore, job?.id]);

  useEffect(() => {
    if (!job?.id) return;
    // Track locally so the explorer table doesn't re-animate this row on return.
    try {
      const raw = sessionStorage.getItem("zync_viewed_jobs");
      const viewed = new Set<string>(raw ? (JSON.parse(raw) as string[]) : []);
      if (!viewed.has(job.id)) {
        viewed.add(job.id);
        sessionStorage.setItem("zync_viewed_jobs", JSON.stringify([...viewed]));
      }
    } catch { /* ignore */ }
    markRead(job.id);
  }, [job?.id, markRead]);

  if (isLoading) {
    return (
      <main className={pageStyles.page}>
        <p className={pageStyles.placeholder} aria-live="polite">{s.loading}</p>
      </main>
    );
  }

  if (isError || !job) {
    return (
      <main className={pageStyles.page}>
        <p className={pageStyles.placeholder}>{s.notFound}</p>
        <Link to="/">{s.backToDashboard}</Link>
      </main>
    );
  }

  const displayJob = localResult ?? job;

  function handleRequestScore(): void {
    requestScore(
      { existing_job_id: job!.id },
      { onSuccess: (result) => setLocalResult(result) },
    );
  }

  function handleNavigateUpload(): void {
    void navigate("/resume-manager");
  }

  return (
    <main className={pageStyles.page}>
      <header className={detailStyles.header}>
        <Link to="/explorer" className={detailStyles.backLink} aria-label={s.backToExplorer}>
          {s.backToExplorer}
        </Link>
        <div className={detailStyles.headerCenter}>
          <h1 className={pageStyles.pageTitle}>{s.title}</h1>
          {activeResume && <ActiveResumeSelector layout="column" />}
        </div>
      </header>
      {/* cardScroll fills remaining height and provides the scroll — the card itself
          has overflow:hidden so it must not be a direct flex-1 child of the page. */}
      <div className={detailStyles.cardScroll}>
        <JobCard
          response={displayJob}
          onRequestScore={handleRequestScore}
          isScoringPending={isScoringPending}
          onNavigateUpload={handleNavigateUpload}
        />
      </div>
    </main>
  );
}
