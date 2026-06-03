import { useEffect, useState } from "react";
import { en } from "@/i18n/en";
import type {
  ExperienceEntry, EducationEntry, ProjectEntry,
  VolunteeringEntry, ResumeRead, ResumeStructuredData,
} from "@/types/resume";
import type { ScalarKey } from "./MetaPanel";
import {
  EMPTY_EDUCATION, EMPTY_EXPERIENCE,
  EMPTY_PROJECT, EMPTY_VOLUNTEERING,
} from "@/types/resume";
import { useUpdateResume } from "@/api/resumeApi";
import { MetaPanel } from "./MetaPanel";
import { StringListSection } from "./StringListSection";
import { ObjectListSection } from "./ObjectListSection";
import type { FieldConfig } from "./ObjectListSection";
import { LanguagesSection } from "./LanguagesSection";
import { ResumeDataErrorBoundary } from "./ResumeDataErrorBoundary";
import styles from "./ResumeEditor.module.css";
import sharedStyles from "./Shared.module.css";

const rm = en.pages.resumeManager;
type EntryRecord = Record<string, string | null>;

const EXP_FIELDS: FieldConfig[] = [
  { key: "title",       label: rm.entryFields.title },
  { key: "company",     label: rm.entryFields.company },
  { key: "start_date",  label: rm.entryFields.startDate },
  { key: "end_date",    label: rm.entryFields.endDate },
  { key: "description", label: rm.entryFields.description, multiline: true, fullWidth: true },
];

const EDU_FIELDS: FieldConfig[] = [
  { key: "degree",          label: rm.entryFields.degree },
  { key: "institution",     label: rm.entryFields.institution },
  { key: "graduation_year", label: rm.entryFields.graduationYear },
];

const PROJ_FIELDS: FieldConfig[] = [
  { key: "name",         label: rm.entryFields.projectName },
  { key: "url",          label: rm.entryFields.projectUrl },
  { key: "technologies", label: rm.entryFields.technologies, fullWidth: true },
  { key: "description",  label: rm.fields.summary, multiline: true, fullWidth: true },
];

const VOL_FIELDS: FieldConfig[] = [
  { key: "organization", label: rm.entryFields.organization },
  { key: "role",         label: rm.entryFields.role },
  { key: "start_date",   label: rm.entryFields.startDate },
  { key: "end_date",     label: rm.entryFields.endDate },
  { key: "description",  label: rm.entryFields.description, multiline: true, fullWidth: true },
];

// Helpers to convert typed entries ↔ EntryRecord (technologies stored comma-joined)
function toRecord(entry: unknown): EntryRecord { return entry as EntryRecord; }
function isEntryEmpty(record: EntryRecord): boolean {
  return Object.values(record).every(v => !v?.trim());
}
function projToRecord(p: ProjectEntry): EntryRecord {
  return { ...p, technologies: p.technologies.join(", ") };
}
function recordToProj(r: EntryRecord): ProjectEntry {
  return {
    name: r["name"] ?? null,
    description: r["description"] ?? null,
    url: r["url"] ?? null,
    technologies: (r["technologies"] ?? "").split(",").map(s => s.trim()).filter(Boolean),
  };
}

interface ResumeEditorProps {
  resume: ResumeRead;
  onSaveSuccess: () => void;
  onSaveError: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}

/**
 * Two-panel editor holding all resume fields as local state.
 * User edits are buffered locally; Save triggers PUT /api/resumes/{id}.
 */
export function ResumeEditor({ resume, onSaveSuccess, onSaveError, onDirtyChange }: ResumeEditorProps): React.JSX.Element {
  const { mutate: saveResume, isPending } = useUpdateResume();

  const initData = (): ResumeStructuredData => {
    const base: ResumeStructuredData = {
      full_name: null, current_role: null, target_role: null,
      email: null, phone: null, location: null,
      linkedin_url: null, github_url: null, portfolio_url: null,
      summary: null, skills: [], experience: [], education: [],
      projects: [], volunteering: [], languages: [], certifications: [],
      ...(resume.structured_data ?? {}),
    };
    return {
      ...base,
      education: [...base.education].sort((a, b) =>
        (b.graduation_year ?? "").localeCompare(a.graduation_year ?? "")
      ),
    };
  };

  const [data, setData] = useState<ResumeStructuredData>(initData);
  const [versionName, setVersionName] = useState(resume.version_name);
  const [versionNameError, setVersionNameError] = useState(false);

  function setDataDirty(updater: (prev: ResumeStructuredData) => ResumeStructuredData): void {
    setData(updater);
    onDirtyChange?.(true);
  }

  function updateVersionName(value: string): void {
    setVersionName(value);
    onDirtyChange?.(true);
  }

  useEffect(() => {
    setData(initData());
    setVersionName(resume.version_name);
    setVersionNameError(false);
    onDirtyChange?.(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resume.id]);

  function setField(field: ScalarKey, value: string): void {
    setData(prev => ({ ...prev, [field]: value || null }));
    onDirtyChange?.(true);
  }

  function save(): void {
    if (!versionName.trim()) { setVersionNameError(true); return; }
    setVersionNameError(false);

    const cleanData: ResumeStructuredData = {
      ...data,
      skills: data.skills.filter(s => s.trim() !== ""),
      certifications: data.certifications.filter(s => s.trim() !== ""),
      experience: data.experience.filter(e => !isEntryEmpty(toRecord(e))),
      education: data.education.filter(e => !isEntryEmpty(toRecord(e))),
      projects: data.projects.filter(p => !isEntryEmpty(projToRecord(p))),
      volunteering: data.volunteering.filter(v => !isEntryEmpty(toRecord(v))),
      languages: data.languages.filter(l => !isEntryEmpty(toRecord(l))),
    };

    saveResume(
      { id: resume.id, payload: { version_name: versionName.trim(), structured_data: cleanData } },
      {
        onSuccess: () => { setData(cleanData); onDirtyChange?.(false); onSaveSuccess(); },
        onError: onSaveError,
      },
    );
  }

  return (
    <div className={styles.editor}>
      <div className={styles.panels}>
        <ResumeDataErrorBoundary>
          <MetaPanel
            versionName={versionName}
            data={data}
            versionNameError={versionNameError}
            onVersionNameChange={updateVersionName}
            onFieldChange={setField}
          />
          <div className={sharedStyles.panel} aria-label="Resume sections">
            <StringListSection
              title={rm.sections.skills}
              items={data.skills}
              itemLabel={rm.entryFields.skill}
              onChange={(v): void => setDataDirty(p => ({ ...p, skills: v }))}
            />
            <ObjectListSection
              title={rm.sections.experience}
              entries={data.experience.map(toRecord)}
              fields={EXP_FIELDS}
              emptyEntry={toRecord(EMPTY_EXPERIENCE)}
              onChange={(recs): void => setDataDirty(p => ({ ...p, experience: recs as unknown as ExperienceEntry[] }))}
            />
            <ObjectListSection
              title={rm.sections.education}
              entries={data.education.map(toRecord)}
              fields={EDU_FIELDS}
              emptyEntry={toRecord(EMPTY_EDUCATION)}
              onChange={(recs): void => setDataDirty(p => ({ ...p, education: recs as unknown as EducationEntry[] }))}
            />
            <ObjectListSection
              title={rm.sections.projects}
              entries={data.projects.map(projToRecord)}
              fields={PROJ_FIELDS}
              emptyEntry={projToRecord(EMPTY_PROJECT)}
              onChange={(recs): void => setDataDirty(p => ({ ...p, projects: recs.map(recordToProj) as ProjectEntry[] }))}
            />
            <ObjectListSection
              title={rm.sections.volunteering}
              entries={data.volunteering.map(toRecord)}
              fields={VOL_FIELDS}
              emptyEntry={toRecord(EMPTY_VOLUNTEERING)}
              onChange={(recs): void => setDataDirty(p => ({ ...p, volunteering: recs as unknown as VolunteeringEntry[] }))}
            />
            <LanguagesSection
              languages={data.languages}
              onChange={(v): void => setDataDirty(p => ({ ...p, languages: v }))}
            />
            <StringListSection
              title={rm.sections.certifications}
              items={data.certifications}
              itemLabel={rm.entryFields.certification}
              onChange={(v): void => setDataDirty(p => ({ ...p, certifications: v }))}
            />
          </div>
        </ResumeDataErrorBoundary>
      </div>

      <div className={styles.footer}>
        <button
          className={styles.saveBtn}
          onClick={save}
          disabled={isPending}
          aria-label={en.common.save}
          aria-busy={isPending}
        >
          {isPending ? en.common.loading : en.common.save}
        </button>
      </div>
    </div>
  );
}
