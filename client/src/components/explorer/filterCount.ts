import type { JobFiltersParams } from "@/types/job";

/**
 * Count how many filters are currently narrowing the job list.
 *
 * Drives the badge on the collapsed Filters panel, so a user whose filters are
 * hidden can still tell at a glance that the grid is not showing everything.
 *
 * @param filters - The active filter params (`q` is ignored; free-text search is
 *   counted from `search` so the debounced and immediate values cannot disagree).
 * @param search - The current free-text search box value.
 * @returns The number of active filters, `0` when the list is unfiltered.
 */
export function countActiveFilters(
  filters: JobFiltersParams,
  search: string,
): number {
  let count = search.trim() ? 1 : 0;

  if (filters.date_from) count += 1;
  if (filters.date_to) count += 1;
  if (filters.min_score !== undefined) count += 1;
  if (filters.role) count += 1;
  if (filters.company) count += 1;
  if (filters.cv_id) count += 1;
  if (filters.source_type) count += 1;
  if (filters.status) count += 1;
  if (filters.min_experience !== undefined) count += 1;
  if (filters.is_new) count += 1;
  if (filters.is_unread) count += 1;
  if (filters.has_cover_letter) count += 1;
  count += filters.skills?.length ?? 0;

  return count;
}
