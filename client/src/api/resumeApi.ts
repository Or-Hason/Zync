import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ResumeListItem, ResumeRead, ResumeUpdate } from "@/types/resume";

const BASE = "/api/resumes";

async function fetchResumes(): Promise<ResumeListItem[]> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Failed to fetch resumes");
  return res.json() as Promise<ResumeListItem[]>;
}

async function uploadResume(file: File, versionName?: string): Promise<ResumeRead> {
  const form = new FormData();
  form.append("file", file);
  if (versionName) form.append("version_name", versionName);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const status = res.status;
    throw Object.assign(new Error("Upload failed"), { status });
  }
  return res.json() as Promise<ResumeRead>;
}

async function fetchResume(id: string): Promise<ResumeRead> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error("Failed to fetch resume");
  return res.json() as Promise<ResumeRead>;
}

async function updateResume(id: string, payload: ResumeUpdate): Promise<ResumeRead> {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Save failed");
  return res.json() as Promise<ResumeRead>;
}

/** React Query key constants. */
export const RESUME_KEYS = {
  list: ["resumes"] as const,
  detail: (id: string) => ["resumes", id] as const,
};

/** Fetch all resumes, newest first. */
export function useResumes(): ReturnType<typeof useQuery<ResumeListItem[]>> {
  return useQuery<ResumeListItem[]>({
    queryKey: RESUME_KEYS.list,
    queryFn: fetchResumes,
  });
}

/**
 * Fetch a single resume by ID (includes structured_data).
 * Skips the query when id is null.
 */
export function useResume(id: string | null): ReturnType<typeof useQuery<ResumeRead>> {
  return useQuery<ResumeRead>({
    queryKey: RESUME_KEYS.detail(id ?? ""),
    queryFn: () => fetchResume(id!),
    enabled: id !== null,
  });
}

/** Upload a new resume file. Primes the detail cache and invalidates the list. */
export function useUploadResume(): ReturnType<
  typeof useMutation<ResumeRead, Error & { status?: number }, { file: File; versionName?: string }>
> {
  const qc = useQueryClient();
  return useMutation<ResumeRead, Error & { status?: number }, { file: File; versionName?: string }>({
    mutationFn: ({ file, versionName }) => uploadResume(file, versionName),
    onSuccess: (resume) => {
      // Prime the detail cache so selecting the just-uploaded resume is instant.
      qc.setQueryData(RESUME_KEYS.detail(resume.id), resume);
      qc.invalidateQueries({ queryKey: RESUME_KEYS.list });
    },
  });
}

/** Persist user corrections to a resume. Invalidates the list on success. */
export function useUpdateResume(): ReturnType<
  typeof useMutation<ResumeRead, Error, { id: string; payload: ResumeUpdate }>
> {
  const qc = useQueryClient();
  return useMutation<ResumeRead, Error, { id: string; payload: ResumeUpdate }>({
    mutationFn: ({ id, payload }) => updateResume(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: RESUME_KEYS.list }),
  });
}
