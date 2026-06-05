import { en } from "@/i18n/en";
import type { JobScrapeResponse, JobRequirements } from "@/types/job";
import styles from "./JobCard.module.css";

const s = en.pages.jobAdd.jobCard;

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

  const showDuplicate = assessment && (assessment.is_duplicate || assessment.duplicate_chance >= 60);

  // Derive banner style from score or advice content
  const getBannerStyle = (): "success" | "warning" | "error" | "info" => {
    if (match_score !== null && match_score < 40) return "error";
    if (system_advice.includes("Not recommended")) return "warning";
    if (match_score !== null && match_score >= 70) return "success";
    return "info";
  };

  const bannerStyle = getBannerStyle();

  // Score badge color
  const getScoreColor = (): string => {
    if (match_score === null) return "neutral";
    if (match_score >= 70) return "green";
    if (match_score >= 40) return "yellow";
    return "red";
  };

  const scoreColor = getScoreColor();

  // Status label
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
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return s.publishedUnknown;
    }
  };

  return (
    <div className={styles.card}>
      <div className={`${styles.banner} ${styles[`banner${bannerStyle}`]}`} role="status">
        {system_advice}
      </div>

      <div className={styles.header}>
        <div className={styles.headerMain}>
          <h2 className={styles.title}>{job_title || "Untitled Job"}</h2>
          {company_name && <p className={styles.company}>{company_name}</p>}
        </div>
        <div className={styles.badges}>
          <div className={`${styles.scoreBadge} ${styles[`scoreBadge${scoreColor}`]}`}>
            {match_score !== null ? match_score : s.notScored}
          </div>
          <div className={styles.statusBadge}>{getStatusLabel()}</div>
        </div>
      </div>

      {showDuplicate && assessment && (
        <div className={styles.duplicateWarning} role="alert">
          <span className={styles.duplicateIcon}>⚠</span>
          <span className={styles.duplicateText}>
            {s.duplicateWarning} {s.duplicateChance.replace("{chance}", String(assessment.duplicate_chance))}
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
            <span className={styles.metaLabel}>{s.publishedLabel}:</span>
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

function RequirementsSection({ requirements }: RequirementsSectionProps): React.JSX.Element {
  const { skills, years_of_experience, education, other } = requirements;
  const hasAny = (skills?.length ?? 0) > 0 || years_of_experience || education || (other?.length ?? 0) > 0;

  if (!hasAny) return <></>;

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>{s.requirementsLabel}</h3>
      <div className={styles.reqList}>
        {skills && skills.length > 0 && (
          <div className={styles.reqItem}>
            <span className={styles.reqLabel}>Skills:</span>
            <div className={styles.skillsList}>
              {skills.map((skill) => (
                <span key={skill} className={`${styles.skill} ${styles.skillRequired}`}>
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}
        {years_of_experience !== undefined && years_of_experience !== null && (
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
    </section>
  );
}
