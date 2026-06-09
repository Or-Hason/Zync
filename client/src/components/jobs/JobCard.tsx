import { useActiveResume } from "@/api/resumeApi";
import { useCheckCachedScore } from "@/api/jobsApi";
import { en } from "@/i18n/en";
import type { JobScrapeResponse } from "@/types/job";
import { JobApplySection } from "./JobApplySection";
import { JobCardBanner, type BannerStyle } from "./JobCardBanner";
import { RequirementsSection } from "./RequirementsSection";
import { ScorePlaceholder } from "./ScorePlaceholder";
import styles from "./JobCard.module.css";

const s = en.pages.jobAdd.jobCard;

type ScoreColor = "green" | "yellow" | "red" | "neutral";

const SCORE_CLASS: Record<ScoreColor, string> = {
  green: styles.scoreBadgeGreen,
  yellow: styles.scoreBadgeYellow,
  red: styles.scoreBadgeRed,
  neutral: styles.scoreBadgeNeutral,
};

interface JobCardProps {
  response: JobScrapeResponse;
  /** Trigger re-scoring with the currently active resume. */
  onRequestScore?: () => void;
  isScoringPending?: boolean;
  /** Navigate to Resume Manager, persisting re-score state. */
  onNavigateUpload?: () => void;
}

/**
 * Displays a parsed job posting.
 * When `match_score` is null and the active resume differs from the scoring resume,
 * a read-only cache check runs automatically. If cached, the score renders
 * immediately; otherwise a ScorePlaceholder with a "Calculate Score" button shows.
 */
export function JobCard({
  response,
  onRequestScore,
  isScoringPending = false,
  onNavigateUpload,
}: JobCardProps): React.JSX.Element {
  const { data: activeResume } = useActiveResume();

  const {
    job_title,
    company_name,
    job_description,
    requirements,
    published_at,
    status,
    match_score: responseMatchScore,
    is_duplicate,
    duplicate_chance,
    rationale: responseRationale,
    matched_skills: responseMatchedSkills,
    missing_skills: responseMissingSkills,
    system_advice,
    scored_by_resume_id,
    source_url,
    application_options,
    recommended_apply_method,
  } = response;

  const activeResumeId = activeResume?.id ?? null;
  // No cache lookup needed when the active resume is the one that produced this score.
  const isCurrentResumeScore =
    activeResumeId !== null && scored_by_resume_id === activeResumeId;
  const cachedQueryEnabled = !isCurrentResumeScore && activeResumeId !== null;

  const { data: cachedScoreData, isFetching: isCacheChecking } = useCheckCachedScore(
    cachedQueryEnabled ? response.id : null,
    cachedQueryEnabled ? activeResumeId : null,
  );

  // Display score: current resume's own score if available, cached score for the
  // new resume once loaded, or the original response score while a check is in flight.
  let match_score: number | null;
  let rationale: string | null | undefined;
  let matched_skills: string[];
  let missing_skills: string[];

  if (isCurrentResumeScore || isCacheChecking) {
    match_score = responseMatchScore;
    rationale = responseRationale;
    matched_skills = responseMatchedSkills ?? [];
    missing_skills = responseMissingSkills ?? [];
  } else if (cachedScoreData) {
    match_score = cachedScoreData.match_score;
    rationale = cachedScoreData.rationale;
    matched_skills = cachedScoreData.matched_skills;
    missing_skills = cachedScoreData.missing_skills;
  } else {
    match_score = null;
    rationale = null;
    matched_skills = [];
    missing_skills = [];
  }

  const hasScore = match_score !== null;
  const showDuplicate = is_duplicate || (duplicate_chance ?? 0) >= 60;

  const getBannerStyle = (): BannerStyle => {
    const advice = system_advice ?? "";
    if (match_score !== null && match_score < 40) return "error";
    if (
      advice.includes("Not recommended") ||
      advice.includes("duplicate") ||
      advice.includes("rejected")
    )
      return "warning";
    if (match_score !== null && match_score >= 70) return "success";
    return "info";
  };

  const getScoreColor = (): ScoreColor => {
    if (match_score === null) return "neutral";
    if (match_score >= 70) return "green";
    if (match_score >= 40) return "yellow";
    return "red";
  };

  const getStatusLabel = (): string => {
    switch (status) {
      case "auto_rejected": return s.statusAutoRejected;
      case "not_applied": return s.statusNotApplied;
      default: return status;
    }
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return s.publishedUnknown;
    try {
      // Bare ISO strings from the backend have no timezone suffix — treat as UTC.
      const utc = /Z|[+-]\d{2}:\d{2}$/.test(dateStr) ? dateStr : `${dateStr}Z`;
      const date = new Date(utc);
      const isMidnightUtc =
        date.getUTCHours() === 0 && date.getUTCMinutes() === 0 && date.getUTCSeconds() === 0;
      return isMidnightUtc
        ? date.toLocaleDateString(undefined, { dateStyle: "medium" })
        : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return s.publishedUnknown;
    }
  };

  const bannerStyle = getBannerStyle();
  // Always show banner: real advice from Gemini, or no-score guidance as fallback.
  const bannerText = system_advice ?? (!hasScore ? s.noScoreAdvice : null);
  const scoreColor = getScoreColor();

  return (
    <div className={styles.card}>
      {bannerText && (
        <JobCardBanner text={bannerText} style={bannerStyle} adviceLabel={s.adviceLabel} />
      )}

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

      <JobApplySection
        sourceUrl={source_url}
        recommendedApplyMethod={recommended_apply_method}
        applicationOptions={application_options}
      />

      {showDuplicate && (
        <div className={styles.duplicateWarning} role="alert">
          <span className={styles.duplicateIcon} aria-hidden="true">⚠</span>
          <span className={styles.duplicateText}>
            <span>{s.duplicateWarning}</span>
            <span className={styles.duplicateChanceText}>
              {s.duplicateChance.replace("{chance}", String(duplicate_chance ?? 0))}
            </span>
          </span>
        </div>
      )}

      {/* Inline spinner while scoring is in progress — visible without scrolling */}
      {isScoringPending && (
        <div className={styles.rescoringIndicator} aria-live="polite">
          <div className={styles.miniSpinner} role="status" aria-label={s.rescoring} />
          <span>{s.rescoring}</span>
        </div>
      )}

      {job_description && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Description</h3>
          <p className={styles.description}>{job_description}</p>
        </section>
      )}

      {requirements && <RequirementsSection requirements={requirements} />}

      {!hasScore && !isScoringPending && onRequestScore !== undefined && (
        <section className={styles.section}>
          <ScorePlaceholder
            onRequestScore={onRequestScore}
            onNavigateUpload={onNavigateUpload ?? ((): void => {})}
            isScoringPending={isScoringPending}
          />
        </section>
      )}

      {published_at && (
        <section className={styles.section}>
          <p className={styles.meta}>
            <span className={styles.metaLabel}>{s.publishedLabel}:</span>{" "}
            {formatDate(published_at)}
          </p>
        </section>
      )}

      {hasScore && (matched_skills?.length ?? 0) > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.matchedSkills}</h3>
          <div className={styles.skillsList}>
            {matched_skills!.map((skill) => (
              <span key={skill} className={`${styles.skill} ${styles.skillMatched}`}>
                {skill}
              </span>
            ))}
          </div>
        </section>
      )}

      {hasScore && (missing_skills?.length ?? 0) > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.missingSkills}</h3>
          <div className={styles.skillsList}>
            {missing_skills!.map((skill) => (
              <span key={skill} className={`${styles.skill} ${styles.skillMissing}`}>
                {skill}
              </span>
            ))}
          </div>
        </section>
      )}

      {hasScore && rationale && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>{s.rationale}</h3>
          <p className={styles.rationale}>{rationale}</p>
        </section>
      )}
    </div>
  );
}
