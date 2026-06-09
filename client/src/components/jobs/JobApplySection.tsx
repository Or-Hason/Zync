import { en } from "@/i18n/en";
import styles from "./JobApplySection.module.css";

const s = en.pages.jobAdd.jobCard;

const DEFAULT_APPLY_METHOD = "Apply via the platform's native button";

/**
 * Opens a URL safely in a new tab, using the Tauri shell plugin when running
 * inside the desktop app and `window.open` otherwise.
 */
function openExternalUrl(url: string): void {
  if (typeof window !== "undefined" && (window as unknown as { __TAURI__?: unknown }).__TAURI__) {
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
 */
export function JobApplySection({
  sourceUrl,
  recommendedApplyMethod,
  applicationOptions = [],
}: JobApplySectionProps): React.JSX.Element {
  const displayApplyMethod = recommendedApplyMethod?.trim() || DEFAULT_APPLY_METHOD;
  const hasOriginalUrl = Boolean(sourceUrl);
  const hasOptions = applicationOptions.length > 0;

  const handleOpenOriginal = (e: React.MouseEvent<HTMLAnchorElement>): void => {
    if (sourceUrl && (window as unknown as { __TAURI__?: unknown }).__TAURI__) {
      e.preventDefault();
      openExternalUrl(sourceUrl);
    }
  };

  return (
    <section className={styles.section}>
      <div className={styles.applyHeader}>
        <div>
          <h3 className={styles.sectionTitle}>{s.recommendedApplyMethod}</h3>
          <p className={styles.applyMethod}>{displayApplyMethod}</p>
        </div>
        {hasOriginalUrl && (
          <a
            href={sourceUrl!}
            onClick={handleOpenOriginal}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={s.viewOriginalJobAriaLabel}
            className={styles.viewOriginalBtn}
          >
            {s.viewOriginalJob}
          </a>
        )}
      </div>

      {hasOptions && (
        <div className={styles.waysToApply}>
          <h4 className={styles.waysTitle}>{s.waysToApply}</h4>
          <div className={styles.optionsList}>
            {applicationOptions.map((option) => {
              const href = resolveHref(option);
              const isMail = href.startsWith("mailto:");
              return (
                <a
                  key={option}
                  href={href}
                  target={isMail ? undefined : "_blank"}
                  rel={isMail ? undefined : "noopener noreferrer"}
                  aria-label={`${s.waysToApplyLinkAriaLabel}: ${option}`}
                  className={styles.optionChip}
                  onClick={
                    !isMail
                      ? (e: React.MouseEvent<HTMLAnchorElement>): void => {
                          if ((window as unknown as { __TAURI__?: unknown }).__TAURI__) {
                            e.preventDefault();
                            openExternalUrl(option);
                          }
                        }
                      : undefined
                  }
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
