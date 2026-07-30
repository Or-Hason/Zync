/**
 * Do-Not-Disturb time window sub-component extracted from NotificationSettingsPanel.
 */

import { useRef } from "react";
import { en } from "@/i18n/en";
import type { NotificationSettings } from "@/api/settingsApi";
import { calculateAutoDndEnd, calculateAutoDndStart } from "./dndTimeUtils";
import styles from "./NotificationSettingsPanel.module.css";

const s = en.pages.settings.notificationsPanel;

interface DndFieldsProps {
  /** Current DND start value from the parent. */
  dndStart: string;
  /** Current DND end value from the parent. */
  dndEnd: string;
  /** Daily digest time used for auto-DND collision avoidance. */
  dailyTime: string;
  /** Whether the mutation is in-flight. */
  isPending: boolean;
  /** Callback to persist partial notification settings. */
  onSave: (partial: Partial<NotificationSettings>) => void;
  /** Notify the parent of DND start value changes. */
  onDndStartChange: (value: string) => void;
  /** Notify the parent of DND end value changes. */
  onDndEndChange: (value: string) => void;
  /** When true, highlight both inputs to indicate a conflict with Daily Digest Time. */
  hasConflict?: boolean;
}

/**
 * Two paired time inputs (Start / End) for the Do-Not-Disturb window.
 * Manages its own refs for DOM-level clearing and auto-calculates the
 * companion field (+/- 8h, capped by Daily Digest time) on blur.
 *
 * @param props - {@link DndFieldsProps}
 * @returns The rendered DND input pair.
 */
export function DndFields({
  dndStart,
  dndEnd,
  dailyTime,
  isPending,
  onSave,
  onDndStartChange,
  onDndEndChange,
  hasConflict = false,
}: DndFieldsProps): React.JSX.Element {
  const dndStartRef = useRef<HTMLInputElement>(null);
  const dndEndRef = useRef<HTMLInputElement>(null);

  /**
   * Force clear partial DOM time input buffer and state when deleting a DND window.
   */
  function clearDndInputs(): void {
    onDndStartChange("");
    onDndEndChange("");
    if (dndStartRef.current) dndStartRef.current.value = "";
    if (dndEndRef.current) dndEndRef.current.value = "";
    onSave({ dnd_start: null, dnd_end: null });
  }

  /**
   * Handle blur events on the DND Start input. Enforces +/-8h pairing or dual deletion.
   */
  function handleDndStartBlur(): void {
    // Rule: If deleted or incomplete (e.g. 06:--), clear both UI buffer and server state
    if (!dndStart) {
      clearDndInputs();
      return;
    }
    // Rule: If user entered Start time and End is empty, automatically add End time (avoiding Daily Digest collision)
    if (dndStart && !dndEnd) {
      const notifyTime = dailyTime;
      const calcEnd = calculateAutoDndEnd(dndStart, notifyTime);
      onDndEndChange(calcEnd);
      if (dndEndRef.current) dndEndRef.current.value = calcEnd;
      onSave({ dnd_start: dndStart, dnd_end: calcEnd });
      return;
    }
    // Both values present
    onSave({ dnd_start: dndStart, dnd_end: dndEnd });
  }

  /**
   * Handle blur events on the DND End input. Enforces +/-8h pairing or dual deletion.
   */
  function handleDndEndBlur(): void {
    // Rule: If deleted or incomplete (e.g. --:30), clear both UI buffer and server state
    if (!dndEnd) {
      clearDndInputs();
      return;
    }
    // Rule: If user entered End time without Start time, automatically set Start time (avoiding Daily Digest collision)
    if (dndEnd && !dndStart) {
      const notifyTime = dailyTime;
      const calcStart = calculateAutoDndStart(dndEnd, notifyTime);
      onDndStartChange(calcStart);
      if (dndStartRef.current) dndStartRef.current.value = calcStart;
      onSave({ dnd_start: calcStart, dnd_end: dndEnd });
      return;
    }
    // Both values present
    onSave({ dnd_start: dndStart, dnd_end: dndEnd });
  }

  return (
    <div className={styles.dndRow}>
      <label className={styles.label}>{s.dndLabel}</label>
      <div className={styles.dndInputs}>
        <div className={styles.dndGroup}>
          <label htmlFor="dnd-start" className={styles.dndGroupLabel}>
            {s.dndStartLabel}
          </label>
          <input
            id="dnd-start"
            ref={dndStartRef}
            className={`${styles.input}${hasConflict ? ` ${styles.conflictInput}` : ""}`}
            type="time"
            value={dndStart}
            disabled={isPending}
            onChange={(e) => onDndStartChange(e.target.value)}
            onBlur={handleDndStartBlur}
          />
        </div>
        <div className={styles.dndGroup}>
          <label htmlFor="dnd-end" className={styles.dndGroupLabel}>
            {s.dndEndLabel}
          </label>
          <input
            id="dnd-end"
            ref={dndEndRef}
            className={`${styles.input}${hasConflict ? ` ${styles.conflictInput}` : ""}`}
            type="time"
            value={dndEnd}
            disabled={isPending}
            onChange={(e) => onDndEndChange(e.target.value)}
            onBlur={handleDndEndBlur}
          />
        </div>
      </div>
    </div>
  );
}
