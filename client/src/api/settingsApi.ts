import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type BypassPreference = "ask" | "always" | "never";

interface BlacklistResponse {
  keywords: string[];
}

interface BypassPreferenceResponse {
  preference: BypassPreference;
}

/** Allowed scan-frequency values (hours). Mirrors the backend Literal. */
export const SCAN_FREQUENCY_CHOICES = [1, 3, 6, 12, 24] as const;

export type ScanFrequencyHours = (typeof SCAN_FREQUENCY_CHOICES)[number];

/** Auto-scan configuration mirroring the backend ScanSettings schema. */
export interface ScanSettings {
  auto_scan_enabled: boolean;
  scan_frequency_hours: ScanFrequencyHours;
  notification_score_threshold: number;
}

const BASE = "/api/settings";

async function fetchBlacklist(): Promise<string[]> {
  const res = await fetch(`${BASE}/blacklist`);
  if (!res.ok) throw new Error("Failed to fetch blacklist");
  const data = (await res.json()) as BlacklistResponse;
  return data.keywords;
}

async function addKeyword(keyword: string): Promise<void> {
  const res = await fetch(`${BASE}/blacklist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword }),
  });
  if (!res.ok) {
    throw Object.assign(new Error("Add keyword failed"), { status: res.status });
  }
}

async function removeKeyword(keyword: string): Promise<void> {
  const res = await fetch(`${BASE}/blacklist/${encodeURIComponent(keyword)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Remove keyword failed");
}

async function fetchBypassPreference(): Promise<BypassPreference> {
  const res = await fetch(`${BASE}/blacklist-bypass-preference`);
  if (!res.ok) throw new Error("Failed to fetch bypass preference");
  const data = (await res.json()) as BypassPreferenceResponse;
  return data.preference;
}

async function setBypassPreference(preference: BypassPreference): Promise<void> {
  const res = await fetch(`${BASE}/blacklist-bypass-preference`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preference }),
  });
  if (!res.ok) throw new Error("Failed to save preference");
}

async function fetchScanSettings(): Promise<ScanSettings> {
  const res = await fetch(`${BASE}/scan`);
  if (!res.ok) throw new Error("Failed to fetch scan settings");
  return res.json() as Promise<ScanSettings>;
}

async function updateScanSettings(payload: ScanSettings): Promise<ScanSettings> {
  const res = await fetch(`${BASE}/scan`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw Object.assign(new Error("Failed to save scan settings"), { status: res.status });
  }
  return res.json() as Promise<ScanSettings>;
}

/** React Query key constants. */
export const SETTINGS_KEYS = {
  blacklist: ["settings", "blacklist"] as const,
  bypassPreference: ["settings", "bypassPreference"] as const,
  scan: ["settings", "scan"] as const,
};

/** Fetch the blacklist keyword list. */
export function useBlacklist(): ReturnType<typeof useQuery<string[]>> {
  return useQuery<string[]>({
    queryKey: SETTINGS_KEYS.blacklist,
    queryFn: fetchBlacklist,
  });
}

/** Add a keyword to the blacklist. Invalidates the list on success. */
export function useAddKeyword(): ReturnType<
  typeof useMutation<void, Error & { status?: number }, string>
> {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: addKeyword,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SETTINGS_KEYS.blacklist });
    },
  });
}

/** Remove a keyword from the blacklist. Invalidates the list on success. */
export function useRemoveKeyword(): ReturnType<
  typeof useMutation<void, Error, string>
> {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: removeKeyword,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SETTINGS_KEYS.blacklist });
    },
  });
}

/** Fetch the current bypass preference. */
export function useBypassPreference(): ReturnType<typeof useQuery<BypassPreference>> {
  return useQuery<BypassPreference>({
    queryKey: SETTINGS_KEYS.bypassPreference,
    queryFn: fetchBypassPreference,
  });
}

/** Persist a new bypass preference. Invalidates the preference query on success. */
export function useSetBypassPreference(): ReturnType<
  typeof useMutation<void, Error, BypassPreference>
> {
  const qc = useQueryClient();
  return useMutation<void, Error, BypassPreference>({
    mutationFn: setBypassPreference,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SETTINGS_KEYS.bypassPreference });
    },
  });
}

/** Fetch the auto-scan configuration. */
export function useScanSettings(): ReturnType<typeof useQuery<ScanSettings>> {
  return useQuery<ScanSettings>({
    queryKey: SETTINGS_KEYS.scan,
    queryFn: fetchScanSettings,
  });
}

/**
 * Persist the auto-scan configuration. Primes the scan cache with the server
 * response so the panel reflects the canonical persisted state immediately.
 */
export function useUpdateScanSettings(): ReturnType<
  typeof useMutation<ScanSettings, Error & { status?: number }, ScanSettings>
> {
  const qc = useQueryClient();
  return useMutation<ScanSettings, Error & { status?: number }, ScanSettings>({
    mutationFn: updateScanSettings,
    onSuccess: (settings) => {
      qc.setQueryData(SETTINGS_KEYS.scan, settings);
    },
  });
}
