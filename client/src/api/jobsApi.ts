import { useMutation, useQuery } from "@tanstack/react-query";
import type { JobScrapeResponse } from "@/types/job";

const BASE = "/api/jobs";

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
