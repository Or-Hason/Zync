import { useState } from "react";
import { en } from "@/i18n/en";
import { useResumes, useUploadResume } from "@/api/resumeApi";
import type { ResumeRead } from "@/types/resume";
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

  const [activeResume, setActiveResume] = useState<ResumeRead | null>(null);
  const [toast, setToast] = useState<ToastState>(null);

  function showToast(message: string, kind: "success" | "error"): void {
    setToast({ message, kind });
  }

  function handleFile(file: File): void {
    upload(
      { file },
      {
        onSuccess: (resume) => {
          setActiveResume(resume);
        },
        onError: (err: Error & { status?: number }) => {
          if (err.status === 415) showToast(rm.uploadInvalidType, "error");
          else if (err.status === 413) showToast(rm.uploadTooLarge, "error");
          else showToast(rm.uploadError, "error");
        },
      },
    );
  }

  function handleSelectResume(id: string): void {
    const found = resumeList.find((r) => r.id === id);
    if (!found) return;
    setActiveResume({
      id: found.id,
      version_name: found.version_name,
      target_role: found.target_role,
      structured_data: null,
      created_at: found.created_at,
    });
  }

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

      {isUploading ? (
        <div className={styles.parsingState} aria-live="polite" aria-label={rm.parsing}>
          <div className={styles.spinner} role="status" aria-label={rm.parsing} />
          <span className={styles.parsingLabel}>{rm.parsing}</span>
          <span className={styles.parsingHint}>{rm.parsingHint}</span>
        </div>
      ) : activeResume ? (
        <>
          <div className={styles.toolbar}>
            <ResumeList
              resumes={resumeList}
              selectedId={activeResume.id}
              onSelect={handleSelectResume}
            />
          </div>
          <ResumeEditor
            resume={activeResume}
            onSaveSuccess={(): void => showToast(rm.saveSuccess, "success")}
            onSaveError={(): void => showToast(rm.saveError, "error")}
          />
        </>
      ) : (
        <>
          <UploadZone onFile={handleFile} />
          {resumeList.length > 0 && (
            <div className={styles.toolbar}>
              <ResumeList
                resumes={resumeList}
                selectedId={null}
                onSelect={handleSelectResume}
              />
            </div>
          )}
        </>
      )}
    </main>
  );
}
