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
  /** ISO-8601 timestamp of the last completed scan; null if none has run. */
  last_scan_at: string | null;
  /** True while a scan (scheduled or manual) is executing. */
  scan_in_progress: boolean;
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

export async function fetchScanSettings(): Promise<ScanSettings> {
  const res = await fetch(`${BASE}/scan`);
  if (!res.ok) throw new Error("Failed to fetch scan settings");
  return res.json() as Promise<ScanSettings>;
}

async function triggerScan(): Promise<void> {
  const res = await fetch(`${BASE}/scan/trigger`, { method: "POST" });
  if (!res.ok) {
    throw Object.assign(new Error("Scan trigger failed"), { status: res.status });
  }
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

/** Fetch the auto-scan configuration (no background polling). */
export function useScanSettings(
  opts: { refetchInterval?: number | false } = {},
): ReturnType<typeof useQuery<ScanSettings>> {
  return useQuery<ScanSettings>({
    queryKey: SETTINGS_KEYS.scan,
    queryFn: fetchScanSettings,
    refetchInterval: opts.refetchInterval,
  });
}

/**
 * Like useScanSettings but with smart polling:
 * - 2 s while a scan is running (fast completion detection)
 * - 10 s while auto_scan is enabled (quickly picks up scheduler-triggered scans)
 * - no polling otherwise
 */
export function useScanStatusPolling(): ReturnType<typeof useQuery<ScanSettings>> {
  return useQuery<ScanSettings>({
    queryKey: SETTINGS_KEYS.scan,
    queryFn: fetchScanSettings,
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return false;
      if (d.scan_in_progress) return 2_000;
      if (d.auto_scan_enabled) return 10_000;
      return false;
    },
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

/** Trigger an immediate background scan. Invalidates the scan cache on success. */
export function useTriggerScan(): ReturnType<
  typeof useMutation<void, Error & { status?: number }, void>
> {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, void>({
    mutationFn: triggerScan,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SETTINGS_KEYS.scan });
    },
  });
}
