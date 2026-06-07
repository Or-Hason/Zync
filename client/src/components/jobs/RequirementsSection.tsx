import { en } from "@/i18n/en";
import type { JobRequirements } from "@/types/job";
import cardStyles from "./JobCard.module.css";
import reqStyles from "./RequirementsSection.module.css";

const s = en.pages.jobAdd.jobCard;

function SkillTags({ items }: { items: string[] }): React.JSX.Element {
  return (
    <div className={cardStyles.skillsList}>
      {items.map((skill) => (
        <span key={skill} className={`${cardStyles.skill} ${reqStyles.skillRequired}`}>
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
    <section className={cardStyles.section}>
      <h3 className={cardStyles.sectionTitle}>{s.requirementsLabel}</h3>
      <div className={reqStyles.reqList}>
        {hasRequired && (
          <div className={reqStyles.reqGroup}>
            <span className={reqStyles.reqGroupTitle}>{s.requiredGroup}</span>
            {skills && skills.length > 0 && (
              <div className={reqStyles.reqItem}>
                <span className={reqStyles.reqLabel}>{s.skillsLabel}:</span>
                <SkillTags items={skills} />
              </div>
            )}
            {other && other.length > 0 && (
              <div className={reqStyles.reqItem}>
                <span className={reqStyles.reqLabel}>{s.other}:</span>
                <ul className={reqStyles.otherList}>
                  {other.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {hasRecommended && (
          <div className={reqStyles.reqGroup}>
            <span className={reqStyles.reqGroupTitle}>{s.recommendedGroup}</span>
            {recommended_skills && recommended_skills.length > 0 && (
              <div className={reqStyles.reqItem}>
                <span className={reqStyles.reqLabel}>{s.skillsLabel}:</span>
                <SkillTags items={recommended_skills} />
              </div>
            )}
            {recommended_other && recommended_other.length > 0 && (
              <div className={reqStyles.reqItem}>
                <span className={reqStyles.reqLabel}>{s.other}:</span>
                <ul className={reqStyles.otherList}>
                  {recommended_other.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {years_of_experience != null && (
          <div className={reqStyles.reqItem}>
            <span className={reqStyles.reqLabel}>{s.yearsOfExperience}:</span>
            <span>{years_of_experience} years</span>
          </div>
        )}

        {education && (
          <div className={reqStyles.reqItem}>
            <span className={reqStyles.reqLabel}>{s.education}:</span>
            <span>{education}</span>
          </div>
        )}
      </div>
    </section>
  );
}
