import { en } from "@/i18n/en";
import type { LanguageEntry } from "@/types/resume";
import { EMPTY_LANGUAGE } from "@/types/resume";
import styles from "./Shared.module.css";

const rm = en.pages.resumeManager;

interface LanguagesSectionProps {
  languages: LanguageEntry[];
  onChange: (languages: LanguageEntry[]) => void;
}

/**
 * Editable list of language + proficiency pairs.
 * Each row has a text input for the language and a text/select for proficiency.
 * @param languages - Current language entries.
 * @param onChange - Called with the updated array on any change.
 */
export function LanguagesSection({ languages, onChange }: LanguagesSectionProps): React.JSX.Element {
  const title = rm.sections.languages;

  function update(index: number, field: keyof LanguageEntry, value: string): void {
    onChange(languages.map((l, i) => i === index ? { ...l, [field]: value } : l));
  }

  function remove(index: number): void {
    onChange(languages.filter((_, i) => i !== index));
  }

  function add(): void {
    onChange([...languages, { ...EMPTY_LANGUAGE }]);
  }

  return (
    <section aria-label={title}>
      <p className={styles.sectionTitle}>{title}</p>
      {languages.map((lang, i) => (
        <div key={i} className={styles.entryCard} style={{ marginBottom: 8 }}>
          <div className={styles.entryGrid}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor={`lang-${i}-language`}>
                {rm.entryFields.language}
              </label>
              <input
                id={`lang-${i}-language`}
                className={styles.input}
                value={lang.language ?? ""}
                onChange={(e): void => update(i, "language", e.target.value)}
                aria-label={`${rm.entryFields.language} ${i + 1}`}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor={`lang-${i}-proficiency`}>
                {rm.entryFields.proficiencyLevel}
              </label>
              <input
                id={`lang-${i}-proficiency`}
                className={styles.input}
                value={lang.proficiency_level ?? ""}
                onChange={(e): void => update(i, "proficiency_level", e.target.value)}
                placeholder="e.g. Native, B2, Intermediate"
                aria-label={`${rm.entryFields.proficiencyLevel} for language ${i + 1}`}
              />
            </div>
          </div>
          <button
            className={styles.removeBtn}
            onClick={(): void => remove(i)}
            aria-label={`${rm.removeEntry} language ${i + 1}`}
          >
            {rm.removeEntry}
          </button>
        </div>
      ))}
      <button className={styles.addBtn} onClick={add} aria-label={`${rm.addEntry} to ${title}`}>
        + {rm.addEntry}
      </button>
    </section>
  );
}
