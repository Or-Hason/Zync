import { useRef } from "react";
import { en } from "@/i18n/en";
import {
  useCoverLetter,
  useGenerateCoverLetter,
  useLetterTemplate,
  useSaveLetterTemplate,
} from "@/api/coverLetterApi";
import { CoverLetterDiffEditor } from "./CoverLetterDiffEditor";
import styles from "./CoverLetterTab.module.css";

const s = en.pages.coverLetter;

interface CoverLetterTabProps {
  jobId: string;
  /** Active resume ID — null when no resume is selected. */
  resumeId: string | null;
}

/**
 * Three-state cover letter tab inside Job Details:
 *  1. No template → upload prompt
 *  2. Template exists, no letter → generate prompt + privacy notice
 *  3. Letter exists → diff viewer
 */
export function CoverLetterTab({ jobId, resumeId }: CoverLetterTabProps): React.JSX.Element {
  const { data: template, isLoading: isLoadingTemplate } = useLetterTemplate();
  const { data: coverLetter, isLoading: isLoadingLetter } = useCoverLetter(
    jobId,
    resumeId ?? undefined,
  );
  const { mutate: saveFile, isPending: isSavingFile } = useSaveLetterTemplate();
  const { mutate: generate, isPending: isGenerating, error: generateError } =
    useGenerateCoverLetter();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const LETTER_ACCEPTED_TYPES = [
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];
  const LETTER_MAX_BYTES = 5 * 1024 * 1024;

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!LETTER_ACCEPTED_TYPES.includes(file.type)) return;
    if (file.size > LETTER_MAX_BYTES) return;
    saveFile(file);
  }

  function handleGenerate(): void {
    if (!resumeId) return;
    generate({ jobId, resumeId });
  }

  if (!resumeId) {
    return (
      <div className={styles.centeredState}>
        <p className={styles.stateHeading}>{s.noResume.heading}</p>
        <p className={styles.stateDescription}>{s.noResume.description}</p>
      </div>
    );
  }

  if (isLoadingTemplate || isLoadingLetter) {
    return (
      <div className={styles.centeredState} aria-live="polite">
        <p className={styles.stateDescription}>{en.common.loading}</p>
      </div>
    );
  }

  const hasTemplate = Boolean(template?.text);

  // State 3: letter already generated
  if (coverLetter) {
    return (
      <div className={styles.editorContainer}>
        <CoverLetterDiffEditor
          originalText={coverLetter.original_template_text ?? ""}
          generatedText={coverLetter.generated_text}
          summary={coverLetter.gemini_summary}
        />
      </div>
    );
  }

  // State 1: no template uploaded
  if (!hasTemplate) {
    return (
      <div className={styles.centeredState}>
        <p className={styles.stateHeading}>{s.noTemplate.heading}</p>
        <p className={styles.stateDescription}>{s.noTemplate.description}</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.docx"
          className={styles.hiddenInput}
          onChange={handleFileSelect}
          aria-label={s.noTemplate.uploadButton}
        />
        <button
          className={styles.primaryBtn}
          onClick={(): void => fileInputRef.current?.click()}
          disabled={isSavingFile}
          aria-label={s.noTemplate.uploadButton}
        >
          {isSavingFile ? s.noTemplate.uploadingButton : s.noTemplate.uploadButton}
        </button>
      </div>
    );
  }

  // State 2: template exists, no letter yet
  const conflictError =
    generateError && (generateError as Error & { status?: number }).status === 409;
  const genericError = generateError && !conflictError;

  return (
    <div className={styles.centeredState}>
      <p className={styles.stateHeading}>{s.noLetter.heading}</p>
      <p className={styles.stateDescription}>{s.noLetter.description}</p>
      <button
        className={styles.primaryBtn}
        onClick={handleGenerate}
        disabled={isGenerating}
        aria-label={s.noLetter.generateButton}
      >
        {isGenerating ? s.noLetter.generatingButton : s.noLetter.generateButton}
      </button>
      <p className={styles.privacyNotice}>{s.noLetter.privacyNotice}</p>
      {conflictError && (
        <p className={styles.errorMsg} role="alert">{s.existsConflict}</p>
      )}
      {genericError && (
        <p className={styles.errorMsg} role="alert">{s.generateError}</p>
      )}
    </div>
  );
}
