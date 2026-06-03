import { useEffect, useRef, useState } from "react";
import { en } from "@/i18n/en";
import styles from "./UploadZone.module.css";

const ACCEPTED_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
const MAX_BYTES = 10 * 1024 * 1024;

interface UploadZoneProps {
  onFile: (file: File) => void;
}

/**
 * Drag-and-drop + click-to-browse upload zone.
 * Validates MIME type and file size client-side before handing off.
 * @param onFile - Called with the validated File object.
 */
export function UploadZone({ onFile }: UploadZoneProps): React.JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  function validate(file: File): string | null {
    if (!ACCEPTED_TYPES.includes(file.type)) return en.pages.resumeManager.uploadInvalidType;
    if (file.size > MAX_BYTES) return en.pages.resumeManager.uploadTooLarge;
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

        const fileName = path.replace(/\\/g, "/").split("/").pop() ?? "resume";
        const ext = fileName.split(".").pop()?.toLowerCase();
        const mime =
          ext === "pdf"
            ? "application/pdf"
            : ext === "docx"
              ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
      aria-label={en.pages.resumeManager.uploadDrop}
      onKeyDown={(e): void => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className={styles.hiddenInput}
        onChange={onInputChange}
        aria-label={en.pages.resumeManager.uploadBrowse}
      />
      <span className={styles.dropText}>{en.pages.resumeManager.uploadDrop}</span>
      <span className={styles.orText}>{en.pages.resumeManager.uploadOr}</span>
      <span className={styles.browseBtn}>{en.pages.resumeManager.uploadBrowse}</span>
      <span className={styles.hint}>{en.pages.resumeManager.uploadHint}</span>
      {validationError && (
        <span className={styles.validationError} role="alert" aria-live="polite">
          {validationError}
        </span>
      )}
    </div>
  );
}
