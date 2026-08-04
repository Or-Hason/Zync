import type { JobScoreEntry } from "@/types/job";

/**
 * Pick which CV's score represents a job in the grid.
 *
 * Priority (when `preferBestMatch` is false — the default):
 *  1. The user's Active Resume, if it has scored this job.
 *  2. Otherwise the CV with the highest `match_score`.
 *
 * When `preferBestMatch` is true the Active Resume is ignored entirely and the
 * highest-scoring CV always wins — this backs the "Show Best Match" toggle.
 *
 * Both the `CV Used` and `Score` columns read from this single function so the
 * displayed name and number can never drift apart.
 *
 * @param scores - Every CV score recorded for the job (may be empty).
 * @param activeResumeId - The currently active resume's ID, or null if unset.
 * @param preferBestMatch - Ignore the active resume and always take the top score.
 * @returns The selected score entry, or null when the job is unscored.
 */
export function selectPrimaryScore(
  scores: JobScoreEntry[],
  activeResumeId: string | null,
  preferBestMatch: boolean,
): JobScoreEntry | null {
  if (scores.length === 0) return null;

  if (!preferBestMatch && activeResumeId !== null) {
    const active = scores.find((s) => s.resume_id === activeResumeId);
    if (active) return active;
  }

  return scores.reduce((best, s) => (s.match_score > best.match_score ? s : best));
}

/**
 * Build the hover tooltip listing every CV that scored a job.
 *
 * @param scores - Every CV score recorded for the job.
 * @param activeResumeId - The currently active resume's ID, or null if unset.
 * @param activeSuffix - Marker appended to the active CV's line (i18n string).
 * @returns A newline-separated `Name — 85%` list, highest score first.
 */
export function buildScoreTooltip(
  scores: JobScoreEntry[],
  activeResumeId: string | null,
  activeSuffix: string,
): string {
  return [...scores]
    .sort((a, b) => b.match_score - a.match_score)
    .map((s) => {
      const name = s.resume_name ?? s.resume_id;
      const marker = s.resume_id === activeResumeId ? ` ${activeSuffix}` : "";
      return `${name}${marker} — ${s.match_score}%`;
    })
    .join("\n");
}
