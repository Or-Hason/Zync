import { en } from "@/i18n/en";
import type { ResumeListItem } from "@/types/resume";
import styles from "./ResumeList.module.css";

interface ResumeListProps {
  resumes: ResumeListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * Dropdown selector for switching between uploaded resumes.
 * @param resumes - Available resume summaries.
 * @param selectedId - Currently active resume id.
 * @param onSelect - Called with the selected resume id.
 */
export function ResumeList({ resumes, selectedId, onSelect }: ResumeListProps): React.JSX.Element {
  if (resumes.length === 0) {
    return <p className={styles.empty}>{en.pages.resumeManager.noResumes}</p>;
  }

  return (
    <div className={styles.wrapper}>
      <label className={styles.label} htmlFor="resume-select">
        {en.pages.resumeManager.selectResume}
      </label>
      <select
        id="resume-select"
        className={styles.select}
        value={selectedId ?? ""}
        onChange={(e): void => onSelect(e.target.value)}
        aria-label={en.pages.resumeManager.selectResume}
      >
        {resumes.map((r) => (
          <option key={r.id} value={r.id}>
            {r.version_name}
            {r.target_role ? ` — ${r.target_role}` : ""}
            {" "}
            ({new Date(r.created_at).toLocaleDateString()})
          </option>
        ))}
      </select>
    </div>
  );
}
