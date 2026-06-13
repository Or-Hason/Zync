import { Link, useParams } from "react-router-dom";
import { useJob } from "@/api/jobsApi";
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
      <JobCard response={job} />
    </main>
  );
}
