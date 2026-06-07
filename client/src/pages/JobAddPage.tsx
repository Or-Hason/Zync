import { useState, useRef } from "react";
import { en } from "@/i18n/en";
import { useScrapeJob, type ScrapeRequest } from "@/api/jobsApi";
import { useBypassPreference, useSetBypassPreference } from "@/api/settingsApi";
import type { JobScrapeResponse } from "@/types/job";
import { JobEntryForm } from "@/components/jobs/JobEntryForm";
import { JobCard } from "@/components/jobs/JobCard";
import { BlacklistBypassModal } from "@/components/jobs/BlacklistBypassModal";
import { NoActiveResumePrompt } from "@/components/jobs/NoActiveResumePrompt";
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

/**
 * Page for manually adding and evaluating jobs.
 * Handles form submission, bypass modals, and partial results on error.
 */
export function JobAddPage(): React.JSX.Element {
  const { mutate: scrape, isPending: isScraping } = useScrapeJob();
  const { data: bypassPreference } = useBypassPreference();
  const { mutate: savePreference } = useSetBypassPreference();

  const scrapeNonceRef = useRef(0);
  const [jobResponse, setJobResponse] = useState<JobScrapeResponse | null>(null);
  const [partialJob, setPartialJob] = useState<JobScrapeResponse | null>(null);
  const [noResumeShown, setNoResumeShown] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [bypassModal, setBypassModal] = useState<ModalState>(null);
  const [pendingRequest, setPendingRequest] = useState<ScrapeRequest | null>(null);
  const [blacklistJobId, setBlacklistJobId] = useState<string | null>(null);

  function showToast(message: string, kind: "success" | "error", duration?: number): void {
    setToast({ message, kind, duration });
  }

  function resetForm(): void {
    setJobResponse(null);
    setPartialJob(null);
    setNoResumeShown(false);
    setPendingRequest(null);
    setBypassModal(null);
    setBlacklistJobId(null);
  }

  function handleScrapeSubmit(payload: ScrapeRequest): void {
    const nonce = ++scrapeNonceRef.current;
    setPendingRequest(payload);
    scrape(payload, {
      onSuccess: (response) => {
        if (nonce !== scrapeNonceRef.current) return;
        setJobResponse(response);
        setPartialJob(null);
        setNoResumeShown(false);
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
            scrape({ ...payload, force_score: true, existing_job_id: jobId ?? undefined });
          } else {
            // Ask before
            setBypassModal({ keyword });
          }
        } else if (err.status === 400 && errData?.error === "no_active_resume") {
          if (errData.job) {
            setPartialJob(errData.job as JobScrapeResponse);
          }
          setNoResumeShown(true);
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

  function handleBypassScoreAnyway(remember: boolean): void {
    if (remember && bypassPreference !== "always") {
      savePreference("always", {
        onSuccess: () => {
          showToast(toastS.preferenceSaved, "success");
        },
      });
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
      savePreference("never", {
        onSuccess: () => {
          showToast(toastS.preferenceSaved, "success");
        },
      });
    }
    setBypassModal(null);
    resetForm();
  }

  const showForm = !jobResponse && !partialJob;
  const showCard = !!jobResponse || (partialJob && noResumeShown);

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
        <ActiveResumeSelector />
      </div>

      {noResumeShown && <NoActiveResumePrompt />}

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
          <JobCard response={jobResponse || partialJob!} />
          <button className={styles.resetButton} onClick={resetForm}>
            {s.entryForm.submitButton}
          </button>
        </div>
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
