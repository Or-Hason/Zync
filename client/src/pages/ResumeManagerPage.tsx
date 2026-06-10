import { useEffect, useState } from "react";
import { useBlocker, useNavigate, useSearchParams } from "react-router-dom";
import { en } from "@/i18n/en";
import {
  useResumes,
  useResume,
  useUploadResume,
  useSetActiveResume,
  useDeleteResume,
  useActiveResume,
} from "@/api/resumeApi";
import { UploadZone } from "@/components/resume/UploadZone";
import { ResumeList } from "@/components/resume/ResumeList";
import { ResumeEditor } from "@/components/resume/ResumeEditor";
import { DeleteResumeModal } from "@/components/resume/DeleteResumeModal";
import { Toast } from "@/components/resume/Toast";
import { RESTORE_KEY } from "./JobAddPage";
import styles from "./ResumeManagerPage.module.css";

const rm = en.pages.resumeManager;

type ToastState = { message: string; kind: "success" | "error" } | null;

/** Full Resume Manager: upload → parse → view/edit → save. */
export function ResumeManagerPage(): React.JSX.Element {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo");

  const { data: resumeList = [] } = useResumes();
  const { data: activeResumeRecord } = useActiveResume();
  const { mutate: upload, isPending: isUploading } = useUploadResume();
  const { mutate: setResumeActive } = useSetActiveResume();
  const { mutate: deleteResume, isPending: isDeleting } = useDeleteResume();

  // activeId drives what is shown in the editor — set after upload or dropdown select.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Block React Router tab navigation when the editor has unsaved changes.
  const blocker = useBlocker(isDirty);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    const ok = window.confirm(rm.unsavedChanges);
    if (ok) { setIsDirty(false); blocker.proceed(); }
    else { blocker.reset(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocker.state]);

  // Block browser refresh / window close when dirty.
  useEffect(() => {
    if (!isDirty) return;
    function handle(e: BeforeUnloadEvent): void { e.preventDefault(); }
    window.addEventListener("beforeunload", handle);
    return () => window.removeEventListener("beforeunload", handle);
  }, [isDirty]);

  function handleUploadNew(): void {
    if (isDirty && !window.confirm(rm.unsavedChanges)) return;
    setIsDirty(false);
    setActiveId(null);
  }

  function handleSelectResume(id: string): void {
    if (isDirty && !window.confirm(rm.unsavedChanges)) return;
    setIsDirty(false);
    setActiveId(id);
  }

  // Fetch the full resume (with structured_data) whenever activeId changes.
  // The upload mutation primes the cache so freshly-uploaded resumes load instantly.
  const { data: activeResume, isLoading: isLoadingResume } = useResume(activeId);

  function showToast(message: string, kind: "success" | "error"): void {
    setToast({ message, kind });
  }

  // The resume shown in the editor is the system-active one when their IDs match.
  const isShownResumeActive =
    activeId !== null && activeResumeRecord?.id === activeId;

  function handleConfirmDelete(): void {
    if (!activeId) return;
    const wasActive = isShownResumeActive;
    deleteResume(activeId, {
      onSuccess: () => {
        setShowDeleteModal(false);
        setIsDirty(false);
        setActiveId(null);
        showToast(wasActive ? rm.delete.successActive : rm.delete.success, "success");
      },
      onError: () => {
        setShowDeleteModal(false);
        showToast(rm.delete.error, "error");
      },
    });
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
              onSelect={handleSelectResume}
            />
            <button
              className={styles.uploadNewBtn}
              onClick={handleUploadNew}
              aria-label={rm.uploadNew}
            >
              {rm.uploadNew}
            </button>
            <button
              className={styles.deleteBtn}
              onClick={(): void => setShowDeleteModal(true)}
              aria-label={rm.delete.buttonAriaLabel}
            >
              {rm.delete.button}
            </button>
          </div>
          <ResumeEditor
            resume={activeResume}
            onSaveSuccess={(): void => {
              showToast(rm.saveSuccess, "success");
              if (returnTo) {
                if (activeId) {
                  setResumeActive(activeId, {
                    onSuccess: () => { navigate(returnTo); },
                    onError: () => {
                      // Active resume was not set — clear autoScore so the restore
                      // effect doesn't attempt scoring without an active resume.
                      const raw = sessionStorage.getItem(RESTORE_KEY);
                      if (raw) {
                        try {
                          const stored = JSON.parse(raw) as Record<string, unknown>;
                          stored["autoScore"] = false;
                          sessionStorage.setItem(RESTORE_KEY, JSON.stringify(stored));
                        } catch { /* ignore */ }
                      }
                      navigate(returnTo);
                    },
                  });
                } else {
                  navigate(returnTo);
                }
              }
            }}
            onSaveError={(): void => showToast(rm.saveError, "error")}
            onDirtyChange={setIsDirty}
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
                onSelect={handleSelectResume}
              />
            </div>
          )}
        </>
      )}

      {showDeleteModal && activeResume && (
        <DeleteResumeModal
          versionName={activeResume.version_name}
          isActive={isShownResumeActive}
          isDeleting={isDeleting}
          onConfirm={handleConfirmDelete}
          onCancel={(): void => setShowDeleteModal(false)}
        />
      )}
    </main>
  );
}
