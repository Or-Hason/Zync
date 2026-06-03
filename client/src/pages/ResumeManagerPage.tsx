import { useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useResume, useUploadResume } from "@/api/resumeApi";
import { UploadZone } from "@/components/resume/UploadZone";
import { ResumeList } from "@/components/resume/ResumeList";
import { ResumeEditor } from "@/components/resume/ResumeEditor";
import { Toast } from "@/components/resume/Toast";
import styles from "./ResumeManagerPage.module.css";

const rm = en.pages.resumeManager;

type ToastState = { message: string; kind: "success" | "error" } | null;

/** Full Resume Manager: upload → parse → view/edit → save. */
export function ResumeManagerPage(): React.JSX.Element {
  const { data: resumeList = [] } = useResumes();
  const { mutate: upload, isPending: isUploading } = useUploadResume();

  // activeId drives what is shown in the editor — set after upload or dropdown select.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>(null);

  // Fetch the full resume (with structured_data) whenever activeId changes.
  // The upload mutation primes the cache so freshly-uploaded resumes load instantly.
  const { data: activeResume, isLoading: isLoadingResume } = useResume(activeId);

  function showToast(message: string, kind: "success" | "error"): void {
    setToast({ message, kind });
  }

  function handleFile(file: File): void {
    upload(
      { file },
      {
        onSuccess: (resume) => setActiveId(resume.id),
        onError: (err: Error & { status?: number }) => {
          if (err.status === 415) showToast(rm.uploadInvalidType, "error");
          else if (err.status === 413) showToast(rm.uploadTooLarge, "error");
          else showToast(rm.uploadError, "error");
        },
      },
    );
  }

  const showParsing = isUploading;
  const showLoading = !isUploading && activeId !== null && isLoadingResume;
  const showEditor = !showParsing && !showLoading && activeResume !== undefined;
  const showUpload = !showParsing && !showLoading && activeResume === undefined;

  return (
    <main className={styles.page}>
      <header className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>{rm.title}</h1>
        <p className={styles.pageSubtitle}>{rm.subtitle}</p>
      </header>

      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={(): void => setToast(null)}
        />
      )}

      {showParsing && (
        <div className={styles.parsingState} aria-live="polite" aria-label={rm.parsing}>
          <div className={styles.spinner} role="status" aria-label={rm.parsing} />
          <span className={styles.parsingLabel}>{rm.parsing}</span>
          <span className={styles.parsingHint}>{rm.parsingHint}</span>
        </div>
      )}

      {showLoading && (
        <div className={styles.parsingState} aria-live="polite" aria-label={en.common.loading}>
          <div className={styles.spinner} role="status" aria-label={en.common.loading} />
          <span className={styles.parsingLabel}>{en.common.loading}</span>
        </div>
      )}

      {showEditor && activeResume && (
        <>
          <div className={styles.toolbar}>
            <ResumeList
              resumes={resumeList}
              selectedId={activeId}
              onSelect={setActiveId}
            />
          </div>
          <ResumeEditor
            resume={activeResume}
            onSaveSuccess={(): void => showToast(rm.saveSuccess, "success")}
            onSaveError={(): void => showToast(rm.saveError, "error")}
          />
        </>
      )}

      {showUpload && (
        <>
          <UploadZone onFile={handleFile} />
          {resumeList.length > 0 && (
            <div className={styles.toolbar}>
              <ResumeList
                resumes={resumeList}
                selectedId={null}
                onSelect={setActiveId}
              />
            </div>
          )}
        </>
      )}
    </main>
  );
}
