import { useState } from "react";
import { en } from "@/i18n/en";
import ReactDiffViewer from "react-diff-viewer-continued";
import styles from "./CoverLetterDiffEditor.module.css";

const s = en.pages.coverLetter.diffEditor;

interface CoverLetterDiffEditorProps {
  originalText: string;
  generatedText: string;
  summary: string | null;
  onSave?: (text: string) => void;
  isSaving?: boolean;
}

/**
 * GitHub-style diff viewer for the generated cover letter.
 * Shows original template vs. AI generated text side-by-side.
 * Includes a Gemini summary bubble, copy, print, and optional save actions.
 */
export function CoverLetterDiffEditor({
  originalText,
  generatedText,
  summary,
  onSave,
  isSaving = false,
}: CoverLetterDiffEditorProps): React.JSX.Element {
  const [mode, setMode] = useState<"diff" | "edit">("diff");
  const [editedText, setEditedText] = useState(generatedText);
  const [copyLabel, setCopyLabel] = useState<string>(s.copyButton);

  const isDirty = editedText !== generatedText;

  function handleCopy(): void {
    const textToCopy = mode === "edit" ? editedText : generatedText;
    void navigator.clipboard.writeText(textToCopy).then(() => {
      setCopyLabel(s.copySuccess);
      setTimeout(() => setCopyLabel(s.copyButton), 2000);
    });
  }

  function handlePrint(): void {
    const text = mode === "edit" ? editedText : generatedText;
    const printDiv = document.createElement("div");
    printDiv.id = "cover-letter-print";
    printDiv.textContent = text;
    document.body.appendChild(printDiv);
    const cleanup = (): void => {
      if (document.body.contains(printDiv)) document.body.removeChild(printDiv);
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.print();
  }

  return (
    <div className={styles.container}>
      {summary && (
        <div className={styles.summaryBubble} aria-label={s.summaryLabel}>
          <span className={styles.summaryIcon} aria-hidden="true">✦</span>
          <p className={styles.summaryText}>{summary}</p>
        </div>
      )}

      <div className={styles.toolbar}>
        <div className={styles.modeToggle}>
          <button
            className={`${styles.modeBtn} ${mode === "diff" ? styles.modeBtnActive : ""}`}
            onClick={(): void => setMode("diff")}
            aria-pressed={mode === "diff"}
          >
            {s.viewToggle}
          </button>
          <button
            className={`${styles.modeBtn} ${mode === "edit" ? styles.modeBtnActive : ""}`}
            onClick={(): void => setMode("edit")}
            aria-pressed={mode === "edit"}
          >
            {s.editToggle}
          </button>
        </div>

        <div className={styles.actions}>
          {mode === "edit" && onSave && isDirty && (
            <button
              className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
              onClick={(): void => onSave(editedText)}
              disabled={isSaving}
              aria-label={s.saveButton}
            >
              {isSaving ? s.savingButton : s.saveButton}
            </button>
          )}
          <button className={styles.actionBtn} onClick={handleCopy} aria-label={s.copyButton}>
            {copyLabel}
          </button>
          <button className={styles.actionBtn} onClick={handlePrint} aria-label={s.printButton}>
            {s.printButton}
          </button>
        </div>
      </div>

      {mode === "diff" && (
        <div className={styles.diffWrapper}>
          <ReactDiffViewer
            oldValue={originalText}
            newValue={generatedText}
            splitView
            leftTitle={s.originalLabel}
            rightTitle={s.generatedLabel}
            useDarkTheme
          />
        </div>
      )}

      {mode === "edit" && (
        <textarea
          className={styles.editArea}
          value={editedText}
          onChange={(e): void => setEditedText(e.target.value)}
          aria-label={s.editPlaceholder}
          placeholder={s.editPlaceholder}
          spellCheck
        />
      )}
    </div>
  );
}
