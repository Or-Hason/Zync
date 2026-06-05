import { useState } from "react";
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

type ToastState = { message: string; kind: "success" | "error" } | null;
type ModalState = { keyword: string } | null;

interface ErrorResponse {
  error?: string;
  matched_keyword?: string;
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

  const [jobResponse, setJobResponse] = useState<JobScrapeResponse | null>(null);
  const [partialJob, setPartialJob] = useState<JobScrapeResponse | null>(null);
  const [noResumeShown, setNoResumeShown] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [bypassModal, setBypassModal] = useState<ModalState>(null);
  const [pendingRequest, setPendingRequest] = useState<ScrapeRequest | null>(null);

  function showToast(message: string, kind: "success" | "error"): void {
    setToast({ message, kind });
  }

  function resetForm(): void {
    setJobResponse(null);
    setPartialJob(null);
    setNoResumeShown(false);
    setPendingRequest(null);
    setBypassModal(null);
  }

  function handleScrapeSubmit(payload: ScrapeRequest): void {
    setPendingRequest(payload);
    scrape(payload, {
      onSuccess: (response) => {
        setJobResponse(response);
        setPartialJob(null);
        setNoResumeShown(false);
        setPendingRequest(null);
      },
      onError: (err: Error & { status?: number; data?: unknown }) => {
        const errData = err.data as ErrorResponse | undefined;
        if (err.status === 422 && errData?.error === "blacklist_hit") {
          const keyword = errData.matched_keyword || "unknown";
          if (bypassPreference === "never") {
            showToast(toastS.rejected, "error");
            resetForm();
          } else if (bypassPreference === "always") {
            // Silently re-submit with force_score: true
            scrape({ ...payload, force_score: true });
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
      handleScrapeSubmit({ ...pendingRequest, force_score: true });
    }
  }

  function handleBypassDiscard(): void {
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
        <div className={styles.headerRight}>
          <ActiveResumeSelector />
        </div>
      </header>

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={(): void => setToast(null)}
        />
      )}

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
