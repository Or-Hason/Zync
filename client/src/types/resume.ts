/** TypeScript interfaces mirroring the backend ResumeStructuredData schema. */

export interface ExperienceEntry {
  title: string | null;
  company: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface EducationEntry {
  degree: string | null;
  institution: string | null;
  graduation_year: string | null;
}

export interface ProjectEntry {
  name: string | null;
  description: string | null;
  url: string | null;
  technologies: string[];
}

export interface VolunteeringEntry {
  organization: string | null;
  role: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
}

export interface LanguageEntry {
  language: string | null;
  proficiency_level: string | null;
}

export interface ResumeStructuredData {
  full_name: string | null;
  current_role: string | null;
  target_role: string | null;
  email: string | null;
  phone: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  summary: string | null;
  skills: string[];
  experience: ExperienceEntry[];
  education: EducationEntry[];
  projects: ProjectEntry[];
  volunteering: VolunteeringEntry[];
  languages: LanguageEntry[];
  certifications: string[];
}

export interface ResumeRead {
  id: string;
  version_name: string;
  target_role: string | null;
  structured_data: ResumeStructuredData | null;
  created_at: string;
}

export interface ResumeListItem {
  id: string;
  version_name: string;
  target_role: string | null;
  created_at: string;
}

export interface ResumeUpdate {
  version_name?: string;
  structured_data?: ResumeStructuredData;
}

/** Empty defaults used when adding new entries. */
export const EMPTY_EXPERIENCE: ExperienceEntry = { title: null, company: null, start_date: null, end_date: null, description: null };
export const EMPTY_EDUCATION: EducationEntry = { degree: null, institution: null, graduation_year: null };
export const EMPTY_PROJECT: ProjectEntry = { name: null, description: null, url: null, technologies: [] };
export const EMPTY_VOLUNTEERING: VolunteeringEntry = { organization: null, role: null, start_date: null, end_date: null, description: null };
export const EMPTY_LANGUAGE: LanguageEntry = { language: null, proficiency_level: null };

export function emptyStructuredData(): ResumeStructuredData {
  return {
    full_name: null, current_role: null, target_role: null,
    email: null, phone: null, location: null,
    linkedin_url: null, github_url: null, portfolio_url: null,
    summary: null,
    skills: [], experience: [], education: [],
    projects: [], volunteering: [], languages: [], certifications: [],
  };
}
