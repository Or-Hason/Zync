import { en } from "@/i18n/en";
import styles from "./Shared.module.css";

const rm = en.pages.resumeManager;

interface StringListSectionProps {
  title: string;
  items: string[];
  itemLabel: string;
  onChange: (items: string[]) => void;
}

/**
 * Editable list of plain strings (skills, certifications).
 * Supports adding and removing entries.
 * @param title - Section heading.
 * @param items - Current string array.
 * @param itemLabel - ARIA label for each item input.
 * @param onChange - Called with the updated array on any change.
 */
export function StringListSection({ title, items, itemLabel, onChange }: StringListSectionProps): React.JSX.Element {
  function update(index: number, value: string): void {
    const next = [...items];
    next[index] = value;
    onChange(next);
  }

  function remove(index: number): void {
    onChange(items.filter((_, i) => i !== index));
  }

  function add(): void {
    onChange([...items, ""]);
  }

  return (
    <section aria-label={title}>
      <p className={styles.sectionTitle}>{title}</p>
      {items.map((item, i) => (
        <div key={i} className={styles.entryCard} style={{ marginBottom: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              className={styles.input}
              value={item}
              onChange={(e): void => update(i, e.target.value)}
              aria-label={`${itemLabel} ${i + 1}`}
            />
            <button
              className={styles.removeBtn}
              onClick={(): void => remove(i)}
              aria-label={`${rm.removeEntry} ${i + 1}`}
            >
              {rm.removeEntry}
            </button>
          </div>
        </div>
      ))}
      <button className={styles.addBtn} onClick={add} aria-label={`${rm.addEntry} to ${title}`}>
        + {rm.addEntry}
      </button>
    </section>
  );
}
