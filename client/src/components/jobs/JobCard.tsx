import { en } from "@/i18n/en";
import type { JobScrapeResponse, JobRequirements } from "@/types/job";
import styles from "./JobCard.module.css";

const s = en.pages.jobAdd.jobCard;

type BannerStyle = "success" | "warning" | "error" | "info";
type ScoreColor = "green" | "yellow" | "red" | "neutral";

// Explicit value -> class maps. Dynamic template lookups (e.g.
// styles[`banner${style}`]) silently resolve to undefined when the casing of
// the runtime value does not match the CSS class name, so the colour classes
// never applied. Mapping explicitly keeps it type-safe and case-correct.
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

const SCORE_CLASS: Record<ScoreColor, string> = {
  green: styles.scoreBadgeGreen,
  yellow: styles.scoreBadgeYellow,
  red: styles.scoreBadgeRed,
  neutral: styles.scoreBadgeNeutral,
};

interface JobCardProps {
  response: JobScrapeResponse;
}

/**
 * Displays a scored job posting with system advice, score badge, details, and skills.
 * @param response - The scrape and evaluation response from the backend.
 */
export function JobCard({ response }: JobCardProps): React.JSX.Element {
  const {
    job_title,
    company_name,
    job_description,
    requirements,
    published_at,
    status,
    match_score,
    rationale,
    matched_skills,
    missing_skills,
    system_advice,
    assessment,
  } = response;

  const showDuplicate =
    assessment && (assessment.is_duplicate || assessment.duplicate_chance >= 60);

  // Derive banner style from score or advice content.
  const getBannerStyle = (): BannerStyle => {
    if (match_score !== null && match_score < 40) return "error";
    if (system_advice.includes("Not recommended")) return "warning";
    if (match_score !== null && match_score >= 70) return "success";
    return "info";
  };

  const bannerStyle = getBannerStyle();

  // Score badge colour band.
  const getScoreColor = (): ScoreColor => {
    if (match_score === null) return "neutral";
    if (match_score >= 70) return "green";
    if (match_score >= 40) return "yellow";
    return "red";
  };

  const scoreColor = getScoreColor();

  const getStatusLabel = (): string => {
    switch (status) {
      case "auto_rejected":
        return s.statusAutoRejected;
      case "not_applied":
        return s.statusNotApplied;
      default:
        return status;
    }
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return s.publishedUnknown;
    try {
      const date = new Date(dateStr);
      // When the backend parses a relative date ("3 hours ago"), the time
      // component will be non-zero; show it. Pure date strings land at midnight UTC.
      const isMidnightUtc =
        date.getUTCHours() === 0 && date.getUTCMinutes() === 0 && date.getUTCSeconds() === 0;
      if (isMidnightUtc) {
        return date.toLocaleDateString(undefined, { dateStyle: "medium" });
      }
      return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return s.publishedUnknown;
    }
  };

  return (
    <div className={styles.card}>
      <div className={`${styles.banner} ${BANNER_CLASS[bannerStyle]}`} role="status" aria-live="polite">
        <span className={styles.bannerIcon} aria-hidden="true">
          {BANNER_ICON[bannerStyle]}
        </span>
        <span className={styles.bannerBody}>
          <span className={styles.bannerLabel}>{s.adviceLabel}</span>
          <span className={styles.bannerText}>{system_advice}</span>
        </span>
      </div>

      <div className={styles.header}>
        <div className={styles.headerMain}>
          <h2 className={styles.title}>{job_title || "Untitled Job"}</h2>
          {requirements?.inferred_role && requirements.inferred_role !== job_title && (
            <p className={styles.role}>
              <span className={styles.rolePrefix}>{s.inferredRolePrefix}</span>{" "}
              {requirements.inferred_role}
            </p>
          )}
          {company_name && <p className={styles.company}>{company_name}</p>}
        </div>
        <div className={styles.badges}>
          <div className={`${styles.scoreBadge} ${SCORE_CLASS[scoreColor]}`}>
            <span className={styles.scoreValue}>
              {match_score !== null ? match_score : s.notScored}
            </span>
            <span className={styles.scoreLabel}>
              {match_score !== null ? s.scoreMatchLabel : s.notScoredLabel}
            </span>
          </div>
          <div className={styles.statusBadge}>{getStatusLabel()}</div>
        </div>
      </div>

      {showDuplicate && assessment && (
        <div className={styles.duplicateWarning} role="alert">
          <span className={styles.duplicateIcon} aria-hidden="true">⚠</span>
          <span className={styles.duplicateText}>
            {s.duplicateWarning}{" "}
            {s.duplicateChance.replace("{chance}", String(assessment.duplicate_chance))}
          </span>
        </div>
      )}

      {job_description && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Description</h3>
          <p className={styles.description}>{job_description}</p>
        </section>
      )}

      {requirements && <RequirementsSection requirements={requirements} />}

      {published_at && (
        <section className={styles.section}>
          <p className={styles.meta}>
            <span className={styles.metaLabel}>{s.publishedLabel}:</span>{" "}
            {formatDate(published_at)}
          </p>
        </section>
      )}

      {matched_skills.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.matchedSkills}</h3>
          <div className={styles.skillsList}>
            {matched_skills.map((skill) => (
              <span key={skill} className={`${styles.skill} ${styles.skillMatched}`}>
                {skill}
              </span>
            ))}
          </div>
        </section>
      )}

      {missing_skills.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.missingSkills}</h3>
          <div className={styles.skillsList}>
            {missing_skills.map((skill) => (
              <span key={skill} className={`${styles.skill} ${styles.skillMissing}`}>
                {skill}
              </span>
            ))}
          </div>
        </section>
      )}

      {rationale && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.rationale}</h3>
          <p className={styles.rationale}>{rationale}</p>
        </section>
      )}
    </div>
  );
}

interface RequirementsSectionProps {
  requirements: JobRequirements;
}

function SkillTags({ items }: { items: string[] }): React.JSX.Element {
  return (
    <div className={styles.skillsList}>
      {items.map((skill) => (
        <span key={skill} className={`${styles.skill} ${styles.skillRequired}`}>
          {skill}
        </span>
      ))}
    </div>
  );
}

function RequirementsSection({ requirements }: RequirementsSectionProps): React.JSX.Element {
  const { skills, recommended_skills, years_of_experience, education, other, recommended_other } =
    requirements;

  const hasRequired = (skills?.length ?? 0) > 0 || (other?.length ?? 0) > 0;
  const hasRecommended = (recommended_skills?.length ?? 0) > 0 || (recommended_other?.length ?? 0) > 0;
  const hasMeta = years_of_experience != null || !!education;

  if (!hasRequired && !hasRecommended && !hasMeta) return <></>;

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{s.requirementsLabel}</h3>
      <div className={styles.reqList}>
        {hasRequired && (
          <div className={styles.reqGroup}>
            <span className={styles.reqGroupTitle}>{s.requiredGroup}</span>
            {skills && skills.length > 0 && (
              <div className={styles.reqItem}>
                <span className={styles.reqLabel}>{s.skillsLabel}:</span>
                <SkillTags items={skills} />
              </div>
            )}
            {other && other.length > 0 && (
              <div className={styles.reqItem}>
                <span className={styles.reqLabel}>{s.other}:</span>
                <ul className={styles.otherList}>
                  {other.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {hasRecommended && (
          <div className={styles.reqGroup}>
            <span className={styles.reqGroupTitle}>{s.recommendedGroup}</span>
            {recommended_skills && recommended_skills.length > 0 && (
              <div className={styles.reqItem}>
                <span className={styles.reqLabel}>{s.skillsLabel}:</span>
                <SkillTags items={recommended_skills} />
              </div>
            )}
            {recommended_other && recommended_other.length > 0 && (
              <div className={styles.reqItem}>
                <span className={styles.reqLabel}>{s.other}:</span>
                <ul className={styles.otherList}>
                  {recommended_other.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {years_of_experience != null && (
          <div className={styles.reqItem}>
            <span className={styles.reqLabel}>{s.yearsOfExperience}:</span>
            <span>{years_of_experience} years</span>
          </div>
        )}
        {education && (
          <div className={styles.reqItem}>
            <span className={styles.reqLabel}>{s.education}:</span>
            <span>{education}</span>
          </div>
        )}
      </div>
    </section>
  );
}
