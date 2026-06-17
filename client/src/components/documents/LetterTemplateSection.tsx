import { useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import { en } from "@/i18n/en";
import { UploadZone } from "@/components/resume/UploadZone";
import {
  useLetterTemplate,
  useSaveLetterTemplate,
  useUpdateLetterTemplateText,
  useDeleteLetterTemplate,
} from "@/api/coverLetterApi";
import styles from "./LetterTemplateSection.module.css";

const s = en.pages.documentsManager.letterTemplate;

const LETTER_ACCEPTED_TYPES = [
  "text/plain",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const LETTER_ACCEPTED_EXTENSIONS = [".txt", ".docx"];
const LETTER_MAX_BYTES = 5 * 1024 * 1024;

/** Inline editor + upload zone for the single personal letter template. */
export function LetterTemplateSection(): React.JSX.Element {
  const { data: template, isLoading } = useLetterTemplate();
  const { mutate: saveFile, isPending: isSavingFile } = useSaveLetterTemplate();
  const { mutate: saveText, isPending: isSavingText } = useUpdateLetterTemplateText();
  const { mutate: deleteTemplate, isPending: isDeleting } = useDeleteLetterTemplate();

  const [editorText, setEditorText] = useState<string>("");
  const [isDirty, setIsDirty] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; error: boolean } | null>(null);

  // Sync editor with loaded template
  useEffect(() => {
    if (template?.text !== undefined) {
      setEditorText(template.text ?? "");
      setIsDirty(false);
    }
  }, [template?.text]);

  const blocker = useBlocker(isDirty);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    const ok = window.confirm(s.unsavedChanges);
    if (ok) { setIsDirty(false); blocker.proceed(); }
    else { blocker.reset(); }
  }, [blocker.state]);

  useEffect(() => {
    if (!isDirty) return;
    function handle(e: BeforeUnloadEvent): void { e.preventDefault(); }
    window.addEventListener("beforeunload", handle);
    return () => window.removeEventListener("beforeunload", handle);
  }, [isDirty]);

  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function flashStatus(text: string, error: boolean): void {
    if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
    setStatusMsg({ text, error });
    statusTimerRef.current = setTimeout(() => setStatusMsg(null), 3000);
  }

  function handleEditorChange(e: React.ChangeEvent<HTMLTextAreaElement>): void {
    setEditorText(e.target.value);
    setIsDirty(true);
  }

  function handleSaveText(): void {
    saveText(editorText, {
      onSuccess: () => { setIsDirty(false); flashStatus(s.saveSuccess, false); },
      onError: () => flashStatus(s.saveError, true),
    });
  }

  function handleDelete(): void {
    deleteTemplate(undefined, {
      onSuccess: () => { setEditorText(""); setIsDirty(false); flashStatus(s.deleteSuccess, false); },
      onError: () => flashStatus(s.deleteError, true),
    });
  }

  function handleDownload(): void {
    const blob = new Blob([editorText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = template?.filename
      ? template.filename.replace(/\.[^.]+$/, ".txt")
      : "letter-template.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleFileUpload(file: File): void {
    saveFile(file, {
      onSuccess: () => flashStatus(s.saveSuccess, false),
      onError: () => flashStatus(s.uploadError, true),
    });
  }

  if (isLoading) {
    return <p className={styles.loading}>{en.common.loading}</p>;
  }

  const hasTemplate = Boolean(template?.text);

  return (
    <div className={styles.container}>
      {statusMsg && (
        <p
          className={`${styles.statusMsg} ${statusMsg.error ? styles.statusError : styles.statusSuccess}`}
          role="status"
          aria-live="polite"
        >
          {statusMsg.text}
        </p>
      )}

      {!hasTemplate && (
        <UploadZone
          onFile={handleFileUpload}
          acceptedTypes={LETTER_ACCEPTED_TYPES}
          acceptedExtensions={LETTER_ACCEPTED_EXTENSIONS}
          maxBytes={LETTER_MAX_BYTES}
          dropText={s.uploadDrop}
          orText={s.uploadOr}
          browseText={s.uploadBrowse}
          hint={s.uploadHint}
          invalidTypeText={s.uploadInvalidType}
          tooLargeText={s.uploadTooLarge}
        />
      )}

      {hasTemplate && (
        <>
          {template?.filename && (
            <p className={styles.filenameLabel}>
              {s.filename.replace("{filename}", template.filename)}
            </p>
          )}
          <textarea
            className={styles.editor}
            value={editorText}
            onChange={handleEditorChange}
            aria-label={s.editorLabel}
            placeholder={s.editorPlaceholder}
            spellCheck
          />
          <div className={styles.actions}>
            <button
              className={styles.saveBtn}
              onClick={handleSaveText}
              disabled={!isDirty || isSavingText}
              aria-label={s.save}
            >
              {isSavingText ? s.saving : s.save}
            </button>
            <button
              className={styles.downloadBtn}
              onClick={handleDownload}
              aria-label={s.download}
            >
              {s.download}
            </button>
            <button
              className={styles.deleteBtn}
              onClick={handleDelete}
              disabled={isDeleting}
              aria-label={s.delete}
            >
              {isDeleting ? s.deleting : s.delete}
            </button>
          </div>
        </>
      )}

      {isSavingFile && (
        <p className={styles.loading} aria-live="polite">{en.common.loading}</p>
      )}
    </div>
  );
}
