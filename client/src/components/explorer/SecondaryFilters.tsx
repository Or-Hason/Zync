import { useState, useMemo } from "react";
import { en } from "@/i18n/en";
import type { JobFiltersParams } from "@/types/job";
import styles from "./SecondaryFilters.module.css";

const f = en.pages.explorer.filters;

interface Props {
  filters: JobFiltersParams;
  allSkills: string[];
  onChange: (patch: Partial<JobFiltersParams>) => void;
}

/**
 * Secondary (collapsible) filter row: skills pills, experience, boolean toggles.
 * The full skill list is fetched once on mount and filtered client-side on input.
 */
export function SecondaryFilters({ filters, allSkills, onChange }: Props): React.JSX.Element {
  const [skillInput, setSkillInput] = useState("");

  const selectedSkills = filters.skills ?? [];

  const skillSuggestions = useMemo(
    () =>
      skillInput.trim().length > 0
        ? allSkills.filter(
            (s) =>
              s.toLowerCase().includes(skillInput.toLowerCase()) &&
              !selectedSkills.includes(s),
          )
        : [],
    [skillInput, allSkills, selectedSkills],
  );

  function addSkill(skill: string): void {
    const trimmed = skill.trim();
    if (!trimmed || selectedSkills.includes(trimmed)) return;
    onChange({ skills: [...selectedSkills, trimmed] });
    setSkillInput("");
  }

  function removeSkill(skill: string): void {
    onChange({ skills: selectedSkills.filter((s) => s !== skill) });
  }

  function handleSkillKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if ((e.key === "Enter" || e.key === ",") && skillInput.trim()) {
      e.preventDefault();
      addSkill(skillInput);
    } else if (e.key === "Backspace" && !skillInput && selectedSkills.length > 0) {
      removeSkill(selectedSkills[selectedSkills.length - 1]);
    }
  }

  return (
    <div className={styles.row} aria-label="Secondary job filters">
      {/* Skills autocomplete pill input */}
      <div className={styles.skillsWrap}>
        <span className={styles.label}>{f.skillsLabel}</span>
        <div className={styles.pillBox}>
          {selectedSkills.map((s) => (
            <span key={s} className={styles.pill}>
              {s}
              <button
                type="button"
                className={styles.pillRemove}
                onClick={(): void => removeSkill(s)}
                aria-label={`Remove skill ${s}`}
              >
                ×
              </button>
            </span>
          ))}
          <div className={styles.skillInputWrap}>
            <input
              type="text"
              className={styles.skillInput}
              placeholder={selectedSkills.length === 0 ? f.skillsPlaceholder : ""}
              value={skillInput}
              onChange={(e): void => setSkillInput(e.target.value)}
              onKeyDown={handleSkillKeyDown}
              list="skill-suggestions"
              aria-label={f.skillsLabel}
            />
            <datalist id="skill-suggestions">
              {skillSuggestions.map((s) => <option key={s} value={s} />)}
            </datalist>
          </div>
        </div>
      </div>

      {/* Min years of experience */}
      <div className={styles.field}>
        <label className={styles.label} htmlFor="minExp">{f.minExperienceLabel}</label>
        <input
          id="minExp"
          type="number"
          className={styles.numInput}
          min={0}
          max={30}
          value={filters.min_experience ?? ""}
          placeholder="0"
          onChange={(e): void =>
            onChange({ min_experience: e.target.value ? Number(e.target.value) : undefined })
          }
          aria-label={f.minExperienceLabel}
        />
      </div>

      {/* Boolean toggles */}
      <div className={styles.toggles}>
        <Toggle
          label={f.isNewLabel}
          checked={!!filters.is_new}
          onChange={(v): void => onChange({ is_new: v || undefined })}
        />
        <Toggle
          label={f.isUnreadLabel}
          checked={!!filters.is_unread}
          onChange={(v): void => onChange({ is_unread: v || undefined })}
        />
        <Toggle
          label={f.hasCoverLetterLabel}
          checked={!!filters.has_cover_letter}
          onChange={(v): void => onChange({ has_cover_letter: v || undefined })}
        />
      </div>

      {/* Source radio */}
      <div className={styles.field}>
        <span className={styles.label}>{f.sourceLabel}</span>
        <select
          className={styles.sourceSelect}
          value={filters.source_type ?? ""}
          onChange={(e): void =>
            onChange({ source_type: (e.target.value as "manual" | "auto") || undefined })
          }
          aria-label={f.sourceLabel}
        >
          <option value="">{f.sourceAll}</option>
          <option value="manual">{f.sourceManual}</option>
          <option value="auto">{f.sourceAuto}</option>
        </select>
      </div>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}): React.JSX.Element {
  return (
    <label className={styles.toggle}>
      <input
        type="checkbox"
        className={styles.toggleInput}
        checked={checked}
        onChange={(e): void => onChange(e.target.checked)}
      />
      <span className={styles.toggleTrack} aria-hidden="true">
        <span className={styles.toggleThumb} />
      </span>
      <span className={styles.toggleLabel}>{label}</span>
    </label>
  );
}
