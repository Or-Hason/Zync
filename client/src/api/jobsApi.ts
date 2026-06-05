import { useMutation } from "@tanstack/react-query";
import type { JobScrapeResponse } from "@/types/job";

const BASE = "/api/jobs";

export interface ScrapeRequest {
  url?: string;
  raw_text?: string;
  force_score?: boolean;
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
