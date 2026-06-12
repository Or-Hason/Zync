import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { en } from "@/i18n/en";
import { useScrapeJob, type ScrapeRequest } from "@/api/jobsApi";
import { useBypassPreference, useSetBypassPreference } from "@/api/settingsApi";
import { useResumes, useActiveResume } from "@/api/resumeApi";
import type { JobScrapeResponse } from "@/types/job";
import { JobEntryForm } from "@/components/jobs/JobEntryForm";
import { JobCard } from "@/components/jobs/JobCard";
import { BlacklistBypassModal } from "@/components/jobs/BlacklistBypassModal";
import { NoActiveResumeModal } from "@/components/jobs/NoActiveResumeModal";
import { ActiveResumeSelector } from "@/components/jobs/ActiveResumeSelector";
import { Toast } from "@/components/resume/Toast";
import { ScanNowButton } from "@/components/jobs/ScanNowButton";
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
 * Handles form submission, blacklist-bypass modals, no-active-resume interception,
 * sessionStorage-based restore after upload navigation, and smart re-scoring.
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

  const [jobResponse, setJobResponse] = useState<JobScrapeResponse | null>(null);
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
        // Resume was just set as active — kick off scoring immediately.
        handleScrapeSubmit({
          ...stored.pendingRequest,
          force_score: true,
          existing_job_id: stored.partialJob.id,
        });
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
    setJobResponse(null);
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
        setJobResponse(response);
        setPartialJob(null);
        setNoResumeModalOpen(false);
        setPendingRequest(null);
      },
      onError: (err: Error & { status?: number; data?: unknown }) => {
        if (nonce !== scrapeNonceRef.current) return;
        const errData = err.data as ErrorResponse | undefined;
        if (err.status === 422 && errData?.error === "blacklist_hit") {
          const keyword = errData.matched_keyword || "unknown";
          const jobId = (errData.job as { id?: string } | undefined)?.id ?? null;
          setBlacklistJobId(jobId);
          if (bypassPreference === "never") {
            showToast(toastS.rejected, "error");
            resetForm();
          } else if (bypassPreference === "always") {
            // Route through handleScrapeSubmit so no_active_resume errors are handled
            handleScrapeSubmit({ ...payload, force_score: true, existing_job_id: jobId ?? undefined });
          } else {
            setBypassModal({ keyword });
          }
        } else if (err.status === 400 && errData?.error === "no_active_resume") {
          if (errData.job) {
            setPartialJob(errData.job as JobScrapeResponse);
          }
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

  /** Re-score the current job (partial or fully scored) with the active resume. */
  function handleRescore(): void {
    const req = originalRequestRef.current;
    if (!req) return;
    const existingId = jobResponse?.id ?? partialJob?.id;
    handleScrapeSubmit({ ...req, force_score: true, existing_job_id: existingId ?? undefined });
  }

  /** Called by NoActiveResumeModal after setActive succeeds. */
  function handleModalCalculateScore(): void {
    handleRescore();
  }

  /**
   * Navigate to Resume Manager, persisting the pending request and partial job
   * in sessionStorage so the page can auto-restore when the user returns.
   */
  function handleNavigateUpload(): void {
    const req = originalRequestRef.current;
    if (req && partialJob) {
      sessionStorage.setItem(
        RESTORE_KEY,
        JSON.stringify({ pendingRequest: req, partialJob, autoScore: true }),
      );
    }
    navigate("/resumes?returnTo=/jobs/add");
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

  const showForm = !jobResponse && !partialJob;
  // Show card once the user dismisses the modal via "View Job Only" (modal closed,
  // partialJob still set) or after a full successful score.
  const showCard = !!jobResponse || (!!partialJob && !noResumeModalOpen);

  return (
    <main className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <h1 className={pageStyles.pageTitle}>{s.title}</h1>
        <p className={pageStyles.pageSubtitle}>{s.subtitle}</p>
      </header>
      <ScanNowButton />

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          duration={toast.duration}
          onDismiss={(): void => setToast(null)}
        />
      )}

      {/* Active resume selector — hidden only on unscored partial-job cards */}
      {(!showCard || !!jobResponse) && (
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
      )}

      {showForm && (
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
      )}

      {showCard && (jobResponse || partialJob) && (
        <div className={styles.cardContainer}>
          <JobCard
            response={jobResponse ?? partialJob!}
            onRequestScore={handleRescore}
            isScoringPending={isScraping}
            onNavigateUpload={handleNavigateUpload}
          />
          <button className={styles.resetButton} onClick={resetForm}>
            {s.entryForm.submitButton}
          </button>
        </div>
      )}

      {noResumeModalOpen && (
        <NoActiveResumeModal
          onViewJobOnly={(): void => setNoResumeModalOpen(false)}
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
