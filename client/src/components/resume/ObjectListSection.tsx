import { en } from "@/i18n/en";
import styles from "./Shared.module.css";

const rm = en.pages.resumeManager;

export interface FieldConfig {
  key: string;
  label: string;
  multiline?: boolean;
  /** Treat field as comma-separated string[] (stored as string, split on save). */
  commaSeparated?: boolean;
  fullWidth?: boolean;
}

type EntryRecord = Record<string, string | null>;

interface ObjectListSectionProps {
  title: string;
  entries: EntryRecord[];
  fields: FieldConfig[];
  emptyEntry: EntryRecord;
  onChange: (entries: EntryRecord[]) => void;
}

/**
 * Generic editable list of object entries (experience, education, projects, volunteering).
 * @param title - Section heading.
 * @param entries - Current array of entry objects.
 * @param fields - Field configuration list defining labels and input behaviour.
 * @param emptyEntry - Blank template used when adding a new entry.
 * @param onChange - Called with the updated array on any change.
 */
export function ObjectListSection({ title, entries, fields, emptyEntry, onChange }: ObjectListSectionProps): React.JSX.Element {
  function updateField(index: number, key: string, value: string): void {
    const next = entries.map((e, i) => i === index ? { ...e, [key]: value } : e);
    onChange(next);
  }

  function remove(index: number): void {
    onChange(entries.filter((_, i) => i !== index));
  }

  function add(): void {
    onChange([...entries, { ...emptyEntry }]);
  }

  return (
    <section aria-label={title}>
      <p className={styles.sectionTitle}>{title}</p>
      {entries.map((entry, i) => (
        <div key={i} className={styles.entryCard} style={{ marginBottom: 10 }}>
          <div className={styles.entryGrid}>
            {fields.filter(f => !f.multiline && !f.fullWidth).map(({ key, label }) => (
              <div key={key} className={styles.field}>
                <label className={styles.label} htmlFor={`${title}-${i}-${key}`}>{label}</label>
                <input
                  id={`${title}-${i}-${key}`}
                  className={styles.input}
                  value={entry[key] ?? ""}
                  onChange={(e): void => updateField(i, key, e.target.value)}
                  aria-label={`${label} for ${title} entry ${i + 1}`}
                />
              </div>
            ))}
          </div>
          {fields.filter(f => f.multiline || f.fullWidth).map(({ key, label, multiline }) => (
            <div key={key} className={styles.field}>
              <label className={styles.label} htmlFor={`${title}-${i}-${key}`}>{label}</label>
              {multiline ? (
                <textarea
                  id={`${title}-${i}-${key}`}
                  className={styles.textarea}
                  value={entry[key] ?? ""}
                  onChange={(e): void => updateField(i, key, e.target.value)}
                  aria-label={`${label} for ${title} entry ${i + 1}`}
                />
              ) : (
                <input
                  id={`${title}-${i}-${key}`}
                  className={styles.input}
                  value={entry[key] ?? ""}
                  onChange={(e): void => updateField(i, key, e.target.value)}
                  aria-label={`${label} for ${title} entry ${i + 1}`}
                />
              )}
            </div>
          ))}
          <button
            className={styles.removeBtn}
            onClick={(): void => remove(i)}
            aria-label={`${rm.removeEntry} from ${title} ${i + 1}`}
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
