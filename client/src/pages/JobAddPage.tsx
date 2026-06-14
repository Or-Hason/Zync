import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { en } from "@/i18n/en";
import { useScrapeJob, type ScrapeRequest } from "@/api/jobsApi";
import { useBypassPreference, useSetBypassPreference } from "@/api/settingsApi";
import { useResumes, useActiveResume } from "@/api/resumeApi";
import type { JobScrapeResponse } from "@/types/job";
import { JobEntryForm } from "@/components/jobs/JobEntryForm";
import { BlacklistBypassModal } from "@/components/jobs/BlacklistBypassModal";
import { NoActiveResumeModal } from "@/components/jobs/NoActiveResumeModal";
import { ActiveResumeSelector } from "@/components/jobs/ActiveResumeSelector";
import { Toast } from "@/components/resume/Toast";
import pageStyles from "./Page.module.css";
import styles from "./JobAddPage.module.css";

const s = en.pages.jobAdd;
const toastS = en.pages.jobAdd.blacklistToasts;

type ToastState = { message: string; kind: "success" | "error"; duration?: number } | null;
type ModalState = { keyword: string } | null;

interface ErrorResponse {
  error?: string;
  matched_keyword?: string;
  message?: string;
  job?: JobScrapeResponse;
}

/** SessionStorage key for restoring a pending job after resume upload. */
export const RESTORE_KEY = "zync_job_restore";

/**
 * Page for manually adding and evaluating jobs.
 * On a successful scrape the user is immediately navigated to /jobs/:id.
 */
export function JobAddPage(): React.JSX.Element {
  const navigate = useNavigate();
  const { mutate: scrape, isPending: isScraping } = useScrapeJob();
  const { data: bypassPreference } = useBypassPreference();
  const { mutate: savePreference } = useSetBypassPreference();
  const { data: resumes = [] } = useResumes();
  const { data: activeResume } = useActiveResume();

  const scrapeNonceRef = useRef(0);
  /** Preserved original request so re-scoring always has the source URL / text. */
  const originalRequestRef = useRef<ScrapeRequest | null>(null);

  /** Partial job saved when no active resume exists — used only for RESTORE_KEY and re-score. */
  const [partialJob, setPartialJob] = useState<JobScrapeResponse | null>(null);
  const [noResumeModalOpen, setNoResumeModalOpen] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [bypassModal, setBypassModal] = useState<ModalState>(null);
  const [pendingRequest, setPendingRequest] = useState<ScrapeRequest | null>(null);
  const [blacklistJobId, setBlacklistJobId] = useState<string | null>(null);

  // Restore state when returning from Resume Manager via ?returnTo=/jobs/add
  useEffect(() => {
    const raw = sessionStorage.getItem(RESTORE_KEY);
    if (!raw) return;
    sessionStorage.removeItem(RESTORE_KEY);
    try {
      const stored = JSON.parse(raw) as {
        pendingRequest: ScrapeRequest;
        partialJob: JobScrapeResponse;
        autoScore?: boolean;
      };
      originalRequestRef.current = stored.pendingRequest;
      setPartialJob(stored.partialJob);
      if (stored.autoScore) {
        // Resume was just set as active — rescore only, skip Ollama and avoid duplicate rows.
        handleScrapeSubmit({ existing_job_id: stored.partialJob.id });
      } else {
        setPendingRequest(stored.pendingRequest);
      }
    } catch {
      // Silently ignore malformed storage data.
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function showToast(message: string, kind: "success" | "error", duration?: number): void {
    setToast({ message, kind, duration });
  }

  function resetForm(): void {
    setPartialJob(null);
    setNoResumeModalOpen(false);
    setPendingRequest(null);
    setBypassModal(null);
    setBlacklistJobId(null);
    originalRequestRef.current = null;
  }

  function handleScrapeSubmit(payload: ScrapeRequest): void {
    const nonce = ++scrapeNonceRef.current;
    if (!originalRequestRef.current) {
      originalRequestRef.current = payload;
    }
    setPendingRequest(payload);
    scrape(payload, {
      onSuccess: (response) => {
        if (nonce !== scrapeNonceRef.current) return;
        void navigate(`/jobs/${response.id}`);
      },
      onError: (err: Error & { status?: number; data?: unknown }) => {
        if (nonce !== scrapeNonceRef.current) return;
        const errData = err.data as ErrorResponse | undefined;
        if (err.status === 422 && errData?.error === "blacklist_hit") {
          const keyword = errData.matched_keyword || "unknown";
          const jobId = (errData.job as { id?: string } | undefined)?.id ?? null;
          setBlacklistJobId(jobId);
          setPendingRequest(payload);
          if (bypassPreference === "never") {
            showToast(toastS.rejected, "error");
            resetForm();
          } else if (bypassPreference === "always") {
            handleScrapeSubmit({ ...payload, force_score: true, existing_job_id: jobId ?? undefined });
          } else {
            setBypassModal({ keyword });
          }
        } else if (err.status === 400 && errData?.error === "no_active_resume") {
          if (errData.job) setPartialJob(errData.job as JobScrapeResponse);
          setNoResumeModalOpen(true);
          setPendingRequest(null);
        } else if (err.status === 422 && errData?.error === "login_wall") {
          showToast(s.errors.loginWall, "error", 6000);
          setPendingRequest(null);
        } else if (err.status === 422 && errData?.error === "irrelevant_content") {
          showToast(s.errors.irrelevantContent, "error", 6000);
          setPendingRequest(null);
        } else if (err.status === 422 && errData?.error === "insufficient_data") {
          showToast(s.errors.insufficientData, "error", 6000);
          setPendingRequest(null);
        } else if (err.status === 502) {
          showToast(s.errors.fetchFailed, "error");
          setPendingRequest(null);
        } else {
          showToast(en.common.error, "error");
          setPendingRequest(null);
        }
      },
    });
  }

  function handleRescore(): void {
    if (!partialJob?.id) return;
    handleScrapeSubmit({ existing_job_id: partialJob.id });
  }

  function handleModalCalculateScore(): void {
    handleRescore();
  }

  /**
   * Navigate to Resume Manager, persisting the pending request and partial job
   * in sessionStorage so the page can auto-restore and re-score when the user returns.
   * returnTo stays /jobs/add so the restore useEffect fires on this page.
   */
  function handleNavigateUpload(): void {
    if (partialJob) {
      // Navigate directly back to the job detail page with a rescore trigger,
      // bypassing the Add Job intermediate step to avoid infinite loading.
      const returnTo = `/jobs/${partialJob.id}?rescore=1`;
      navigate(`/resumes?returnTo=${encodeURIComponent(returnTo)}`);
    } else {
      navigate("/resumes?returnTo=/jobs/add");
    }
  }

  function handleBypassScoreAnyway(remember: boolean): void {
    if (remember && bypassPreference !== "always") {
      savePreference("always", { onSuccess: () => showToast(toastS.preferenceSaved, "success") });
    }
    setBypassModal(null);
    if (pendingRequest) {
      handleScrapeSubmit({
        ...pendingRequest,
        force_score: true,
        existing_job_id: blacklistJobId ?? undefined,
      });
    }
  }

  function handleBypassDiscard(remember: boolean): void {
    if (remember && bypassPreference !== "never") {
      savePreference("never", { onSuccess: () => showToast(toastS.preferenceSaved, "success") });
    }
    setBypassModal(null);
    resetForm();
  }

  return (
    <main className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <h1 className={pageStyles.pageTitle}>{s.title}</h1>
        <p className={pageStyles.pageSubtitle}>{s.subtitle}</p>
      </header>

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          duration={toast.duration}
          onDismiss={(): void => setToast(null)}
        />
      )}

      <div className={styles.resumeSelectorWrap}>
        {resumes.length === 0 ? (
          <button
            className={styles.uploadResumeTopBtn}
            onClick={(): void => { void navigate("/resumes"); }}
            aria-label={s.noActiveResume.uploadToScoreButton}
          >
            {s.noActiveResume.uploadToScoreButton}
          </button>
        ) : (
          <>
            {!activeResume && (
              <p className={styles.selectorNote}>{s.noActiveResume.selectorNote}</p>
            )}
            <ActiveResumeSelector />
          </>
        )}
      </div>

      <div className={styles.formContainer}>
        {isScraping ? (
          <div className={styles.loadingState} aria-live="polite" aria-label={en.common.loading}>
            <div className={styles.spinner} role="status" aria-label={en.common.loading} />
            <span className={styles.loadingLabel}>{s.entryForm.extracting}</span>
          </div>
        ) : (
          <JobEntryForm onSubmit={handleScrapeSubmit} isLoading={false} />
        )}
      </div>

      {noResumeModalOpen && (
        <NoActiveResumeModal
          onViewJobOnly={(): void => {
            if (partialJob) {
              void navigate(`/jobs/${partialJob.id}`);
            } else {
              setNoResumeModalOpen(false);
            }
          }}
          onNavigateUpload={handleNavigateUpload}
          onCalculateScore={handleModalCalculateScore}
          isScoringPending={isScraping}
        />
      )}

      {bypassModal && (
        <BlacklistBypassModal
          keyword={bypassModal.keyword}
          onScoreAnyway={handleBypassScoreAnyway}
          onDiscard={handleBypassDiscard}
        />
      )}
    </main>
  );
}
