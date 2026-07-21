import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CoverLetterRead {
  id: string;
  job_id: string;
  resume_id: string;
  original_template_text: string | null;
  generated_text: string;
  gemini_summary: string | null;
  created_at: string;
}

export interface LetterTemplate {
  text: string | null;
  filename: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const BASE = "/api";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

// ── Cover Letter ──────────────────────────────────────────────────────────────

/** Fetch the existing cover letter for a job+resume pair, or null if 404. */
async function fetchCoverLetter(
  jobId: string,
  resumeId: string,
): Promise<CoverLetterRead | null> {
  try {
    return await fetchJson<CoverLetterRead>(
      `${BASE}/jobs/${jobId}/cover-letter?resume_id=${resumeId}`,
    );
  } catch (err) {
    if ((err as Error & { status?: number }).status === 404) return null;
    throw err;
  }
}

/**
 * Query hook: loads cover letter for a job+resume pair.
 * Returns null when none exists yet; undefined while loading.
 */
export function useCoverLetter(
  jobId: string | null | undefined,
  resumeId: string | null | undefined,
): ReturnType<typeof useQuery<CoverLetterRead | null>> {
  return useQuery<CoverLetterRead | null>({
    queryKey: ["cover-letter", jobId, resumeId],
    queryFn: () => fetchCoverLetter(jobId!, resumeId!),
    enabled: Boolean(jobId && resumeId),
    staleTime: 60_000,
  });
}

/** Mutation hook: update the generated text of an existing cover letter (user edits). */
export function useUpdateCoverLetter(): ReturnType<
  typeof useMutation<CoverLetterRead, Error & { status?: number }, { jobId: string; resumeId: string; generatedText: string }>
> {
  const qc = useQueryClient();
  return useMutation<
    CoverLetterRead,
    Error & { status?: number },
    { jobId: string; resumeId: string; generatedText: string }
  >({
    mutationFn: ({ jobId, resumeId, generatedText }) =>
      fetchJson<CoverLetterRead>(
        `${BASE}/jobs/${jobId}/cover-letter?resume_id=${resumeId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ generated_text: generatedText }),
        },
      ),
    onSuccess: (data) => {
      qc.setQueryData(["cover-letter", data.job_id, data.resume_id], data);
    },
  });
}

/** Mutation hook: generate a cover letter via POST. */
export function useGenerateCoverLetter(): ReturnType<
  typeof useMutation<CoverLetterRead, Error & { status?: number }, { jobId: string; resumeId: string }>
> {
  const qc = useQueryClient();
  return useMutation<
    CoverLetterRead,
    Error & { status?: number },
    { jobId: string; resumeId: string }
  >({
    mutationFn: ({ jobId, resumeId }) =>
      fetchJson<CoverLetterRead>(
        `${BASE}/jobs/${jobId}/cover-letter?resume_id=${resumeId}`,
        { method: "POST" },
      ),
    onSuccess: (data) => {
      qc.setQueryData(["cover-letter", data.job_id, data.resume_id], data);
    },
  });
}

// ── Letter Template ───────────────────────────────────────────────────────────

async function fetchLetterTemplate(): Promise<LetterTemplate> {
  return fetchJson<LetterTemplate>(`${BASE}/settings/letter-template`);
}

/** Query hook: loads the letter template from settings. */
export function useLetterTemplate(): ReturnType<typeof useQuery<LetterTemplate>> {
  return useQuery<LetterTemplate>({
    queryKey: ["letter-template"],
    queryFn: fetchLetterTemplate,
    staleTime: 30_000,
  });
}

/** Mutation hook: upload and save a new letter template file. */
export function useSaveLetterTemplate(): ReturnType<
  typeof useMutation<void, Error & { status?: number }, File>
> {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, File>({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/settings/letter-template`, {
        method: "PUT",
        body: form,
      });
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & { status: number };
        err.status = res.status;
        throw err;
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["letter-template"] });
    },
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

/** Mutation hook: update the letter template text directly from the inline editor. */
export function useUpdateLetterTemplateText(): ReturnType<
  typeof useMutation<LetterTemplate, Error & { status?: number }, string>
> {
  const qc = useQueryClient();
  return useMutation<LetterTemplate, Error & { status?: number }, string>({
    mutationFn: (text: string) =>
      fetchJson<LetterTemplate>(`${BASE}/settings/letter-template`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(["letter-template"], data);
    },
  });
}

/** Mutation hook: delete the letter template. */
export function useDeleteLetterTemplate(): ReturnType<
  typeof useMutation<void, Error & { status?: number }, void>
> {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, void>({
    mutationFn: () =>
      fetch(`${BASE}/settings/letter-template`, { method: "DELETE" }).then(
        (r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); },
      ),
    onSuccess: () => {
      qc.setQueryData(["letter-template"], { text: null, filename: null });
    },
  });
}
