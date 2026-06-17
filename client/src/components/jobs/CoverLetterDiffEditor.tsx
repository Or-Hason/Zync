import { useState } from "react";
import { en } from "@/i18n/en";
import ReactDiffViewer from "react-diff-viewer-continued";
import styles from "./CoverLetterDiffEditor.module.css";

const s = en.pages.coverLetter.diffEditor;

interface CoverLetterDiffEditorProps {
  originalText: string;
  generatedText: string;
  summary: string | null;
}

/**
 * GitHub-style diff viewer for the generated cover letter.
 * Shows original template vs. AI generated text side-by-side.
 * Includes a Gemini summary bubble and copy/download actions.
 */
export function CoverLetterDiffEditor({
  originalText,
  generatedText,
  summary,
}: CoverLetterDiffEditorProps): React.JSX.Element {
  const [mode, setMode] = useState<"diff" | "edit">("diff");
  const [editedText, setEditedText] = useState(generatedText);
  const [copyLabel, setCopyLabel] = useState<string>(s.copyButton);

  function handleCopy(): void {
    const textToCopy = mode === "edit" ? editedText : generatedText;
    void navigator.clipboard.writeText(textToCopy).then(() => {
      setCopyLabel(s.copySuccess);
      setTimeout(() => setCopyLabel(s.copyButton), 2000);
    });
  }

  function handleDownloadPdf(): void {
    const textContent = mode === "edit" ? editedText : generatedText;
    const escaped = textContent
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    const html =
      `<!DOCTYPE html><html><head><title>Cover Letter</title><style>` +
      `body{font-family:serif;font-size:12pt;line-height:1.6;padding:40px;white-space:pre-wrap;}` +
      `@media print{body{padding:0;}}</style></head><body>${escaped}</body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const iframe = document.createElement("iframe");
    iframe.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
    iframe.src = url;
    document.body.appendChild(iframe);
    iframe.addEventListener("load", () => {
      iframe.contentWindow?.print();
      document.body.removeChild(iframe);
      URL.revokeObjectURL(url);
    });
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
          <button className={styles.actionBtn} onClick={handleCopy} aria-label={s.copyButton}>
            {copyLabel}
          </button>
          <button className={styles.actionBtn} onClick={handleDownloadPdf} aria-label={s.downloadButton}>
            {s.downloadButton}
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
            useDarkTheme={false}
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
