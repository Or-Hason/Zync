import { useState, useRef } from "react";
import { en } from "@/i18n/en";
import { useBlacklist, useAddKeyword, useRemoveKeyword } from "@/api/settingsApi";
import { Toast } from "@/components/resume/Toast";
import styles from "./BlacklistPanel.module.css";

const s = en.pages.settings.blacklist;
const KEYWORD_MAX_LENGTH = 50;

type ToastState = { message: string; kind: "success" | "error" } | null;

/**
 * Panel for managing blacklist keywords: fetch, add, and remove.
 * @returns The rendered blacklist management panel.
 */
export function BlacklistPanel(): React.JSX.Element {
  const { data: keywords, isLoading, isError } = useBlacklist();
  const { mutate: addKw, isPending: isAdding } = useAddKeyword();
  const { mutate: removeKw } = useRemoveKeyword();

  const [inputValue, setInputValue] = useState("");
  const [toast, setToast] = useState<ToastState>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function showToast(message: string, kind: "success" | "error"): void {
    setToast({ message, kind });
  }

  function handleAdd(): void {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    addKw(trimmed, {
      onSuccess: () => {
        setInputValue("");
        showToast(`"${trimmed}" ${s.addedSuffix}`, "success");
        inputRef.current?.focus();
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          showToast(s.duplicateError, "error");
        } else {
          showToast(en.common.error, "error");
        }
      },
    });
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === "Enter") handleAdd();
  }

  function handleRemove(keyword: string): void {
    removeKw(keyword, {
      onSuccess: () => showToast(`"${keyword}" ${s.removedSuffix}`, "success"),
      onError: () => showToast(en.common.error, "error"),
    });
  }

  const atLimit = inputValue.length >= KEYWORD_MAX_LENGTH;

  return (
    <section className={styles.panel} aria-labelledby="blacklist-title">
      {toast && (
        <Toast
          message={toast.message}
          kind={toast.kind}
          onDismiss={(): void => setToast(null)}
        />
      )}

      <div className={styles.panelHeader}>
        <h2 id="blacklist-title" className={styles.panelTitle}>{s.title}</h2>
        <p className={styles.panelSubtitle}>{s.subtitle}</p>
      </div>

      <div className={styles.addBlock}>
        <div className={styles.addRow}>
          <input
            ref={inputRef}
            className={styles.input}
            type="text"
            value={inputValue}
            placeholder={s.inputPlaceholder}
            maxLength={KEYWORD_MAX_LENGTH}
            aria-label={s.inputAriaLabel}
            onChange={(e): void => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isAdding}
          />
          <button
            className={styles.addButton}
            onClick={handleAdd}
            disabled={isAdding || !inputValue.trim()}
            aria-label={s.addButtonAriaLabel}
          >
            {en.common.add}
          </button>
        </div>
        {inputValue.length > 0 && (
          <span className={`${styles.charCount} ${atLimit ? styles.charCountLimit : ""}`}>
            {inputValue.length}/{KEYWORD_MAX_LENGTH}
          </span>
        )}
      </div>

      {isLoading && (
        <div className={styles.skeletonWrap} aria-label={s.loading} aria-busy="true">
          {[1, 2, 3, 4].map((n) => (
            <span key={n} className={styles.skeletonChip} />
          ))}
        </div>
      )}

      {isError && (
        <p className={styles.errorState} role="alert">{s.fetchError}</p>
      )}

      {!isLoading && !isError && keywords !== undefined && (
        keywords.length === 0 ? (
          <p className={styles.emptyState}>{s.emptyState}</p>
        ) : (
          <div className={styles.chipsWrap} role="list" aria-label={s.title}>
            {keywords.map((kw) => (
              <span key={kw} className={styles.chip} role="listitem">
                <span className={styles.chipLabel}>{kw}</span>
                <button
                  className={styles.chipRemove}
                  onClick={(): void => handleRemove(kw)}
                  aria-label={`${s.removeKeywordLabel}: ${kw}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )
      )}
    </section>
  );
}
