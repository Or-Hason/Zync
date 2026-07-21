import { useState } from "react";
import { en } from "@/i18n/en";
import {
  useCoverLetter,
  useGenerateCoverLetter,
  useLetterTemplate,
  useSaveLetterTemplate,
  useUpdateCoverLetter,
} from "@/api/coverLetterApi";
import { UploadZone } from "@/components/resume/UploadZone";
import { CoverLetterDiffEditor } from "./CoverLetterDiffEditor";
import styles from "./CoverLetterTab.module.css";

const s = en.pages.coverLetter;

const LETTER_ACCEPTED_TYPES = [
  "text/plain",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const LETTER_ACCEPTED_EXTENSIONS = [".txt", ".docx"];
const LETTER_MAX_BYTES = 5 * 1024 * 1024;

interface CoverLetterTabProps {
  jobId: string;
  /** Active resume ID — null when no resume is selected. */
  resumeId: string | null;
}

/**
 * Three-state cover letter tab inside Job Details:
 *  1. No template → drag-and-drop upload zone
 *  2. Template exists, no letter → generate prompt + privacy notice
 *  3. Letter exists → diff viewer
 */
export function CoverLetterTab({ jobId, resumeId }: CoverLetterTabProps): React.JSX.Element {
  const { data: template, isLoading: isLoadingTemplate } = useLetterTemplate();
  const { data: coverLetter, isLoading: isLoadingLetter } = useCoverLetter(
    jobId,
    resumeId ?? undefined,
  );
  const { mutate: saveFile, isPending: isSavingFile, error: uploadError, reset: resetUpload } =
    useSaveLetterTemplate();
  const { mutate: generate, isPending: isGenerating, error: generateError } =
    useGenerateCoverLetter();
  const { mutate: updateLetter, isPending: isSavingLetter } = useUpdateCoverLetter();

  const [uploadErrorDismissed, setUploadErrorDismissed] = useState(false);

  function handleFileUpload(file: File): void {
    setUploadErrorDismissed(false);
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
          onSave={(text): void => updateLetter({ jobId, resumeId: resumeId!, generatedText: text })}
          isSaving={isSavingLetter}
        />
      </div>
    );
  }

  // State 1: no template uploaded — full drag-and-drop zone
  if (!hasTemplate) {
    const showUploadError = Boolean(uploadError) && !uploadErrorDismissed;
    return (
      <div className={styles.uploadState}>
        <p className={styles.stateHeading}>{s.noTemplate.heading}</p>
        <p className={styles.stateDescription}>{s.noTemplate.description}</p>
        {isSavingFile ? (
          <p className={styles.stateDescription} aria-live="polite">
            {s.noTemplate.uploadingButton}
          </p>
        ) : (
          <UploadZone
            onFile={handleFileUpload}
            acceptedTypes={LETTER_ACCEPTED_TYPES}
            acceptedExtensions={LETTER_ACCEPTED_EXTENSIONS}
            maxBytes={LETTER_MAX_BYTES}
            dropText={s.noTemplate.uploadButton}
            orText={en.pages.documentsManager.letterTemplate.uploadOr}
            browseText={en.pages.documentsManager.letterTemplate.uploadBrowse}
            hint={en.pages.documentsManager.letterTemplate.uploadHint}
            invalidTypeText={s.noTemplate.uploadInvalidType}
            tooLargeText={s.noTemplate.uploadTooLarge}
          />
        )}
        {showUploadError && (
          <p
            className={styles.errorMsg}
            role="alert"
            onClick={(): void => { setUploadErrorDismissed(true); resetUpload(); }}
          >
            {s.noTemplate.uploadError}
          </p>
        )}
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
