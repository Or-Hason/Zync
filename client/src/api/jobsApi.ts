import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JobFiltersParams, JobListItem, JobScrapeResponse } from "@/types/job";

const JOB_DETAIL_STALE_MS = 5 * 60 * 1000; // 5 min — serves notification deep-links from cache
const SKILLS_STALE_MS = 5 * 60 * 1000; // skills change rarely

const BASE = "/api/jobs";

export const JOBS_KEYS = {
  list: (params: JobFiltersParams) => ["jobs", "list", params] as const,
  skills: ["jobs", "skills"] as const,
};

export interface ScrapeRequest {
  url?: string;
  raw_text?: string;
  force_score?: boolean;
  existing_job_id?: string;
}

export interface ScrapeError {
  error?: string;
  matched_keyword?: string;
  job?: unknown;
  message?: string;
  status: number;
}

async function scrapeJob(payload: ScrapeRequest): Promise<JobScrapeResponse> {
  const res = await fetch(`${BASE}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await res.json()) as unknown;
  if (!res.ok) {
    throw Object.assign(new Error("Scrape failed"), {
      status: res.status,
      data,
    });
  }
  return data as JobScrapeResponse;
}

/**
 * Mutate to scrape and evaluate a job posting.
 * On success: returns the full JobScrapeResponse with scoring and advice.
 * On error: the error object has .status and .data properties.
 */
export function useScrapeJob(): ReturnType<
  typeof useMutation<JobScrapeResponse, Error & { status?: number; data?: unknown }, ScrapeRequest>
> {
  return useMutation<JobScrapeResponse, Error & { status?: number; data?: unknown }, ScrapeRequest>({
    mutationFn: scrapeJob,
  });
}

/** Cached score returned by the read-only cache-check endpoint. */
export interface CachedScoreResult {
  match_score: number;
  rationale: string | null;
  matched_skills: string[];
  missing_skills: string[];
}

async function checkCachedScore(
  jobId: string,
  resumeId: string,
): Promise<CachedScoreResult | null> {
  const res = await fetch(
    `${BASE}/${encodeURIComponent(jobId)}/cached-score?resume_id=${encodeURIComponent(resumeId)}`,
  );
  if (!res.ok) return null;
  const data = (await res.json()) as { cached: boolean } & Partial<CachedScoreResult>;
  return data.cached ? (data as CachedScoreResult) : null;
}

async function fetchJob(id: string): Promise<JobScrapeResponse> {
  const res = await fetch(`${BASE}/${encodeURIComponent(id)}`);
  if (!res.ok) {
    throw Object.assign(new Error("Job not found"), { status: res.status });
  }
  return res.json() as Promise<JobScrapeResponse>;
}

/**
 * Fetch a single job by ID.
 * Uses a 5-minute staleTime so the notification deep-link renders from cache
 * without a redundant network request when the user just received the event.
 *
 * @param id - Job UUID, or null to disable the query.
 */
export function useJob(id: string | null): ReturnType<typeof useQuery<JobScrapeResponse>> {
  return useQuery<JobScrapeResponse>({
    queryKey: ["jobs", id],
    queryFn: () => fetchJob(id!),
    enabled: id !== null,
    staleTime: JOB_DETAIL_STALE_MS,
  });
}

/**
 * Read-only cache check for a (job, resume) pair.
 * No DB writes, no Gemini calls. Enabled only when both IDs are non-null.
 *
 * @param jobId - The job's UUID, or null to disable the query.
 * @param resumeId - The resume's UUID, or null to disable the query.
 * @returns Query result containing a CachedScoreResult or null on miss.
 */
export function useCheckCachedScore(
  jobId: string | null,
  resumeId: string | null,
): ReturnType<typeof useQuery<CachedScoreResult | null>> {
  return useQuery<CachedScoreResult | null>({
    queryKey: ["jobs", jobId, "cached-score", resumeId],
    queryFn: () => checkCachedScore(jobId!, resumeId!),
    enabled: jobId !== null && resumeId !== null,
    staleTime: 30_000,
  });
}

async function fetchJobs(params: JobFiltersParams): Promise<JobListItem[]> {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.period && params.period !== "all-time") qs.set("period", params.period);
  if (params.min_score !== undefined) qs.set("min_score", String(params.min_score));
  if (params.role) qs.set("role", params.role);
  if (params.company) qs.set("company", params.company);
  if (params.cv_id) qs.set("cv_id", params.cv_id);
  if (params.source_type) qs.set("source_type", params.source_type);
  if (params.has_cover_letter) qs.set("has_cover_letter", "true");
  if (params.is_new) qs.set("is_new", "true");
  if (params.is_unread) qs.set("is_unread", "true");
  if (params.skills?.length) params.skills.forEach((s) => qs.append("skills", s));
  if (params.min_experience !== undefined) qs.set("min_experience", String(params.min_experience));
  if (params.status) qs.set("status", params.status);

  const path = qs.toString() ? `${BASE}?${qs.toString()}` : BASE;
  const res = await fetch(path);
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json() as Promise<JobListItem[]>;
}

async function fetchJobSkills(): Promise<string[]> {
  const res = await fetch(`${BASE}/skills`);
  if (!res.ok) throw new Error("Failed to fetch job skills");
  return res.json() as Promise<string[]>;
}

/** Fetch the Explorer job list, re-fetching whenever filter params change. */
export function useJobs(params: JobFiltersParams): ReturnType<typeof useQuery<JobListItem[]>> {
  return useQuery<JobListItem[]>({
    queryKey: JOBS_KEYS.list(params),
    queryFn: () => fetchJobs(params),
    staleTime: 0,
  });
}

async function markJobRead(jobId: string): Promise<void> {
  await fetch(`${BASE}/${encodeURIComponent(jobId)}/read`, { method: "PATCH" });
}

/** Mark a job as read when the user opens its detail view. Invalidates the Explorer list. */
export function useMarkJobRead(): ReturnType<typeof useMutation<void, Error, string>> {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: markJobRead,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["jobs", "list"] });
    },
  });
}

/** Fetch all distinct skill strings from DB requirements JSONB (for autocomplete). */
export function useJobSkills(): ReturnType<typeof useQuery<string[]>> {
  return useQuery<string[]>({
    queryKey: JOBS_KEYS.skills,
    queryFn: fetchJobSkills,
    staleTime: SKILLS_STALE_MS,
  });
}
