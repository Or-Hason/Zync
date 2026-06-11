import { en } from "@/i18n/en";
import styles from "./JobApplySection.module.css";

const s = en.pages.jobAdd.jobCard;

const DEFAULT_APPLY_METHOD = "Apply via the platform's native button";

/** True when running inside the Tauri desktop shell. */
const isTauri = typeof window !== "undefined" && "__TAURI__" in window;

/**
 * Opens a URL in the system browser. Uses the Tauri shell plugin in the
 * desktop app; falls back to window.open in the web browser.
 */
function openExternalUrl(url: string): void {
  if (isTauri) {
    import("@tauri-apps/plugin-shell").then(({ open }) => open(url)).catch(() => {
      window.open(url, "_blank", "noopener,noreferrer");
    });
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/** Resolve an option string to a mailto: href or an external URL. */
function resolveHref(option: string): string {
  return option.includes("@") && !option.startsWith("http")
    ? `mailto:${option}`
    : option;
}

interface JobApplySectionProps {
  sourceUrl?: string | null;
  recommendedApplyMethod?: string | null;
  applicationOptions?: string[];
}

/**
 * Renders the "How to Apply" label (plain text enum), optional "View Original
 * Job" button, and clickable chips for every entry in `applicationOptions`.
 *
 * In Tauri, external links are rendered as <button> elements to prevent the
 * webview from intercepting target="_blank" anchors and opening a second tab
 * alongside the Tauri shell plugin's own open() call.
 */
export function JobApplySection({
  sourceUrl,
  recommendedApplyMethod,
  applicationOptions = [],
}: JobApplySectionProps): React.JSX.Element {
  const displayApplyMethod = recommendedApplyMethod?.trim() || DEFAULT_APPLY_METHOD;
  const hasOriginalUrl = Boolean(sourceUrl);
  const hasOptions = applicationOptions.length > 0;

  return (
    <section className={styles.section}>
      <div className={styles.applyHeader}>
        <div>
          <h3 className={styles.sectionTitle}>{s.recommendedApplyMethod}</h3>
          <p className={styles.applyMethod}>{displayApplyMethod}</p>
        </div>
        {hasOriginalUrl && (
          isTauri ? (
            <button
              type="button"
              className={styles.viewOriginalBtn}
              aria-label={s.viewOriginalJobAriaLabel}
              onClick={(): void => openExternalUrl(sourceUrl!)}
            >
              {s.viewOriginalJob}
            </button>
          ) : (
            <a
              href={sourceUrl!}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={s.viewOriginalJobAriaLabel}
              className={styles.viewOriginalBtn}
            >
              {s.viewOriginalJob}
            </a>
          )
        )}
      </div>

      {hasOptions && (
        <div className={styles.waysToApply}>
          <h4 className={styles.waysTitle}>{s.waysToApply}</h4>
          <div className={styles.optionsList}>
            {applicationOptions.map((option) => {
              const href = resolveHref(option);
              const isMail = href.startsWith("mailto:");
              if (!isMail && isTauri) {
                return (
                  <button
                    key={option}
                    type="button"
                    className={styles.optionChip}
                    aria-label={`${s.waysToApplyLinkAriaLabel}: ${option}`}
                    onClick={(): void => openExternalUrl(option)}
                  >
                    {option}
                  </button>
                );
              }
              return (
                <a
                  key={option}
                  href={href}
                  target={isMail ? undefined : "_blank"}
                  rel={isMail ? undefined : "noopener noreferrer"}
                  aria-label={`${s.waysToApplyLinkAriaLabel}: ${option}`}
                  className={styles.optionChip}
                >
                  {option}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
