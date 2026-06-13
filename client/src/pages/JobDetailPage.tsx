import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useJob, useMarkJobRead } from "@/api/jobsApi";
import { JobCard } from "@/components/jobs/JobCard";
import { en } from "@/i18n/en";
import styles from "./Page.module.css";
import detailStyles from "./JobDetailPage.module.css";

const s = en.pages.jobDetail;

/**
 * Deep-link destination for job-match notifications.
 *
 * Loads the job from the React Query cache when available (staleTime 5 min),
 * falling back to GET /api/jobs/:id. Renders the existing JobCard so the full
 * scoring breakdown is visible without re-running the pipeline.
 */
export function JobDetailPage(): React.JSX.Element {
  const { id } = useParams<{ id: string }>();
  const { data: job, isLoading, isError } = useJob(id ?? null);
  const { mutate: markRead } = useMarkJobRead();

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
    // Update notified_at on the server so the Unread filter stops matching this job.
    markRead(job.id);
  }, [job?.id, markRead]);

  if (isLoading) {
    return (
      <main className={styles.page}>
        <p className={styles.placeholder} aria-live="polite">
          {s.loading}
        </p>
      </main>
    );
  }

  if (isError || !job) {
    return (
      <main className={styles.page}>
        <p className={styles.placeholder}>{s.notFound}</p>
        <Link to="/">{s.backToDashboard}</Link>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <Link to="/explorer" className={detailStyles.backLink} aria-label={s.backToExplorer}>
          {s.backToExplorer}
        </Link>
        <h1 className={styles.pageTitle}>{s.title}</h1>
      </header>
      {/* cardScroll fills remaining height and provides the scroll — the card itself
          has overflow:hidden so it must not be a direct flex-1 child of the page. */}
      <div className={detailStyles.cardScroll}>
        <JobCard response={job} />
      </div>
    </main>
  );
}
