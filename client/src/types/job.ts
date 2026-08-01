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

/** One CV's match score for a job, from the `job_scores` bridging table. */
export interface JobScoreEntry {
  resume_id: string;
  resume_name: string | null;
  match_score: number;
}

/**
 * A job as rendered in the Explorer grid.
 *
 * There is no flat `match_score`: a job holds one score per CV, and which one
 * the grid surfaces depends on the active CV / "Show Best Match" toggle. Use
 * `selectPrimaryScore` rather than reading `scores` positionally.
 */
export interface JobListItem {
  id: string;
  job_title: string | null;
  company_name: string | null;
  status: string;
  source_type: string;
  created_at: string;
  /** Every CV that has scored this job, highest score first. */
  scores: JobScoreEntry[];
  requirements: JobRequirements | null;
  has_cover_letter: boolean;
  is_unread: boolean;
}

/**
 * A job row as fed to the Explorer grid.
 *
 * `primaryScore` is resolved once per render pass from the active resume and the
 * "Show Best Match" toggle. It lives on the row rather than being computed
 * inside a column accessor because TanStack memoises accessor results in
 * `row._valuesCache` and never invalidates them when the accessor changes —
 * recomputing here changes the `data` identity, which is what rebuilds the row
 * model (and therefore the sort order too).
 */
export interface JobRow extends JobListItem {
  primaryScore: JobScoreEntry | null;
}

export interface JobFiltersParams {
  q?: string;
  date_from?: string;
  date_to?: string;
  min_score?: number;
  role?: string;
  company?: string;
  cv_id?: string;
  source_type?: "manual" | "auto";
  has_cover_letter?: boolean;
  is_new?: boolean;
  is_unread?: boolean;
  skills?: string[];
  min_experience?: number;
  status?: string;
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
