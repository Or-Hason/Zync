import { useState } from "react";
import { en } from "@/i18n/en";
import type { ScrapeRequest } from "@/api/jobsApi";
import styles from "./JobEntryForm.module.css";

const s = en.pages.jobAdd.entryForm;

type Tab = "url" | "text";

interface JobEntryFormProps {
  onSubmit: (payload: ScrapeRequest) => void;
  isLoading: boolean;
}

/**
 * Job entry form with URL/Paste Text toggle.
 * Submitting calls the scrape mutation.
 * @param onSubmit - Called with the scrape request payload.
 * @param isLoading - Whether the request is in progress.
 */
export function JobEntryForm({ onSubmit, isLoading }: JobEntryFormProps): React.JSX.Element {
  const [tab, setTab] = useState<Tab>("url");
  const [urlValue, setUrlValue] = useState("");
  const [textValue, setTextValue] = useState("");
  const [error, setError] = useState("");

  function handleTabChange(newTab: Tab): void {
    setTab(newTab);
    if (newTab === "url") {
      setTextValue("");
    } else {
      setUrlValue("");
    }
    setError("");
  }

  function handleSubmit(e: React.FormEvent): void {
    e.preventDefault();
    setError("");

    const urlTrimmed = urlValue.trim();
    const textTrimmed = textValue.trim();

    if (tab === "url" && !urlTrimmed) {
      setError(s.emptyError);
      return;
    }
    if (tab === "text" && !textTrimmed) {
      setError(s.emptyError);
      return;
    }

    const payload: ScrapeRequest = tab === "url" ? { url: urlTrimmed } : { raw_text: textTrimmed };
    onSubmit(payload);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tab} ${tab === "url" ? styles.tabActive : ""}`}
          onClick={(): void => handleTabChange("url")}
          disabled={isLoading}
          aria-label={s.tabUrl}
        >
          {s.tabUrl}
        </button>
        <button
          type="button"
          className={`${styles.tab} ${tab === "text" ? styles.tabActive : ""}`}
          onClick={(): void => handleTabChange("text")}
          disabled={isLoading}
          aria-label={s.tabText}
        >
          {s.tabText}
        </button>
      </div>

      <div className={styles.inputWrap}>
        {tab === "url" ? (
          <input
            type="url"
            className={styles.input}
            placeholder={s.urlPlaceholder}
            value={urlValue}
            onChange={(e): void => setUrlValue(e.target.value)}
            disabled={isLoading}
            aria-label={s.urlPlaceholder}
          />
        ) : (
          <textarea
            className={`${styles.input} ${styles.textarea}`}
            placeholder={s.textPlaceholder}
            value={textValue}
            onChange={(e): void => setTextValue(e.target.value)}
            disabled={isLoading}
            aria-label={s.textPlaceholder}
          />
        )}
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        className={styles.submitButton}
        disabled={isLoading}
        aria-label={s.submitButton}
      >
        {s.submitButton}
      </button>
    </form>
  );
}
