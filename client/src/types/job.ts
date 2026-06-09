/** Job scrape and evaluation response.
 *
 * Scoring fields (rationale, matched_skills, missing_skills, system_advice,
 * score_cached) are optional because the backend returns a plain JobRead object
 * (without those fields) in the HTTP 400 "no_active_resume" error body.
 */
export interface JobScrapeResponse {
  id: string;
  job_title: string | null;
  company_name: string | null;
  job_description: string | null;
  requirements: JobRequirements | null;
  published_at: string | null;
  source_url: string | null;
  status: string;
  match_score: number | null;
  scored_by_resume_id?: string | null;
  /** Flat field from JobRead — NOT nested under `assessment`. */
  is_duplicate?: boolean;
  duplicate_chance?: number | null;
  rationale?: string | null;
  matched_skills?: string[];
  missing_skills?: string[];
  system_advice?: string | null;
  score_cached?: boolean;
  application_options?: string[];
  recommended_apply_method?: string | null;
}

export interface JobRequirements {
  inferred_role?: string | null;
  skills?: string[];
  recommended_skills?: string[];
  years_of_experience?: number | null;
  education?: string | null;
  other?: string[];
  recommended_other?: string[];
}
