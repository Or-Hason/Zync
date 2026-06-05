/** Job scrape and evaluation response. */
export interface JobScrapeResponse {
  job_id: string;
  job_title: string | null;
  company_name: string | null;
  job_description: string | null;
  requirements: JobRequirements | null;
  published_at: string | null;
  source_url: string | null;
  status: string;
  match_score: number | null;
  rationale: string | null;
  matched_skills: string[];
  missing_skills: string[];
  system_advice: string;
  score_cached: boolean;
  assessment: {
    is_duplicate: boolean;
    duplicate_chance: number;
  };
}

export interface JobRequirements {
  skills?: string[];
  years_of_experience?: number | null;
  education?: string | null;
  other?: string[];
}
