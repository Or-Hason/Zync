import styles from "./JobCardBanner.module.css";

export type BannerStyle = "success" | "warning" | "error" | "info";

const BANNER_CLASS: Record<BannerStyle, string> = {
  success: styles.bannerSuccess,
  warning: styles.bannerWarning,
  error: styles.bannerError,
  info: styles.bannerInfo,
};

const BANNER_ICON: Record<BannerStyle, string> = {
  success: "✓",
  warning: "⚠",
  error: "✕",
  info: "ℹ",
};

interface JobCardBannerProps {
  text: string;
  style: BannerStyle;
  /** Short uppercase label rendered above the advice text (e.g. "Advice"). */
  adviceLabel: string;
}

/** System-advice callout banner rendered at the top of a JobCard. */
export function JobCardBanner({ text, style, adviceLabel }: JobCardBannerProps): React.JSX.Element {
  return (
    <div
      className={`${styles.banner} ${BANNER_CLASS[style]}`}
      role="status"
      aria-live="polite"
    >
      <span className={styles.bannerIcon} aria-hidden="true">
        {BANNER_ICON[style]}
      </span>
      <span className={styles.bannerBody}>
        <span className={styles.bannerLabel}>{adviceLabel}</span>
        <span className={styles.bannerText}>{text}</span>
      </span>
    </div>
  );
}
