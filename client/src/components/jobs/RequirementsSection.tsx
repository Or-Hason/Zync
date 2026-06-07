import { en } from "@/i18n/en";
import type { JobRequirements } from "@/types/job";
import styles from "./JobCard.module.css";

const s = en.pages.jobAdd.jobCard;

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

interface RequirementsSectionProps {
  requirements: JobRequirements;
}

/**
 * Renders the hierarchical Required / Recommended requirements inside a JobCard.
 * Skills (concrete technologies) and Other (soft skills / domain knowledge) are
 * displayed in separate sub-labels within each group.
 */
export function RequirementsSection({ requirements }: RequirementsSectionProps): React.JSX.Element {
  const { skills, recommended_skills, years_of_experience, education, other, recommended_other } =
    requirements;

  const hasRequired = (skills?.length ?? 0) > 0 || (other?.length ?? 0) > 0;
  const hasRecommended =
    (recommended_skills?.length ?? 0) > 0 || (recommended_other?.length ?? 0) > 0;
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
