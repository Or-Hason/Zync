import { useEffect, useRef, useState } from "react";
import { en } from "@/i18n/en";
import styles from "./UploadZone.module.css";

const RESUME_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
const RESUME_EXTENSIONS = [".pdf", ".docx"];
const RESUME_MAX_BYTES = 10 * 1024 * 1024;

interface UploadZoneProps {
  onFile: (file: File) => void;
  /** MIME types to accept. Defaults to PDF + DOCX (resume use case). */
  acceptedTypes?: string[];
  /** File extensions for the <input accept> attribute. Defaults to .pdf + .docx. */
  acceptedExtensions?: string[];
  /** Max file size in bytes. Defaults to 10 MB. */
  maxBytes?: number;
  dropText?: string;
  orText?: string;
  browseText?: string;
  hint?: string;
  invalidTypeText?: string;
  tooLargeText?: string;
}

/**
 * Drag-and-drop + click-to-browse upload zone.
 * Validates MIME type and file size client-side before handing off.
 * Accepts configurable file types; defaults to the resume (PDF/DOCX) use case.
 *
 * @param onFile - Called with the validated File object.
 */
export function UploadZone({
  onFile,
  acceptedTypes = RESUME_TYPES,
  acceptedExtensions = RESUME_EXTENSIONS,
  maxBytes = RESUME_MAX_BYTES,
  dropText = en.pages.resumeManager.uploadDrop,
  orText = en.pages.resumeManager.uploadOr,
  browseText = en.pages.resumeManager.uploadBrowse,
  hint = en.pages.resumeManager.uploadHint,
  invalidTypeText = en.pages.resumeManager.uploadInvalidType,
  tooLargeText = en.pages.resumeManager.uploadTooLarge,
}: UploadZoneProps): React.JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  function validate(file: File): string | null {
    if (!acceptedTypes.includes(file.type)) return invalidTypeText;
    if (file.size > maxBytes) return tooLargeText;
    return null;
  }

  function handleFile(file: File): void {
    const err = validate(file);
    if (err) { setValidationError(err); return; }
    setValidationError(null);
    onFile(file);
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  // Stable ref so the Tauri listener always calls the latest handleFile
  const handleFileRef = useRef(handleFile);
  useEffect(() => { handleFileRef.current = handleFile; });

  // Tauri WebView2 suppresses browser drop events — use the native Tauri API instead.
  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    let unlisten: (() => void) | undefined;
    let mounted = true;

    void (async () => {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      const { invoke } = await import("@tauri-apps/api/core");

      const unl = await getCurrentWindow().onDragDropEvent(async (event) => {
        const p = event.payload as { type: string; paths?: string[] };
        if (p.type === "hover") { setDragging(true); return; }
        if (p.type === "leave" || p.type !== "drop") { setDragging(false); return; }
        setDragging(false);
        const path = (p.paths ?? [])[0];
        if (!path) return;

        const fileName = path.replace(/\\/g, "/").split("/").pop() ?? "file";
        const ext = fileName.split(".").pop()?.toLowerCase();
        const mime =
          ext === "pdf"
            ? "application/pdf"
            : ext === "docx"
              ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              : ext === "txt"
                ? "text/plain"
                : "";
        try {
          const bytes: number[] = await invoke<number[]>("read_file_bytes", { path });
          handleFileRef.current(new File([new Uint8Array(bytes)], fileName, { type: mime }));
        } catch (err) {
          console.error("Tauri read_file_bytes failed:", err);
        }
      });

      if (mounted) { unlisten = unl; } else { unl(); }
    })();

    return () => { mounted = false; unlisten?.(); };
  }, []);

  return (
    <div
      className={`${styles.zone} ${dragging ? styles.dragging : ""}`}
      onDragOver={(e): void => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(): void => setDragging(false)}
      onDrop={onDrop}
      onClick={(): void => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      aria-label={dropText}
      onKeyDown={(e): void => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={acceptedExtensions.join(",")}
        className={styles.hiddenInput}
        onChange={onInputChange}
        aria-label={browseText}
      />
      <span className={styles.dropText}>{dropText}</span>
      <span className={styles.orText}>{orText}</span>
      <span className={styles.browseBtn}>{browseText}</span>
      <span className={styles.hint}>{hint}</span>
      {validationError && (
        <span className={styles.validationError} role="alert" aria-live="polite">
          {validationError}
        </span>
      )}
    </div>
  );
}
