import { en } from "@/i18n/en";
import styles from "./JobTable.module.css";

const t = en.pages.explorer.table;

interface Props {
  showBestMatch: boolean;
  onChange: (value: boolean) => void;
}

/**
 * The `CV Used` column header, with its mode control built in.
 *
 * The control sits here rather than in the filter panel because it is not a
 * filter — it changes *which CV's* score the CV Used and Score columns show, so
 * it belongs against the columns it governs.
 *
 * It renders the current mode as short words rather than as a
 * bare switch: an unlabelled toggle in a table header gives no clue what it
 * does, and there is no room for a full caption in this column.
 *
 * @param showBestMatch - True when the grid is ignoring the active CV.
 * @param onChange - Called with the next mode when the control is clicked.
 */
export function CvUsedHeader({ showBestMatch, onChange }: Props): React.JSX.Element {
  return (
    <span className={styles.cvHeaderWrap}>
      <span className={styles.cvHeaderLabel}>{t.columnCv}</span>
      <button
        type="button"
        className={`${styles.cvModeBtn} ${showBestMatch ? styles.cvModeBtnOn : ""}`}
        // The header cell is not sortable, so nothing else claims this click —
        // stopping propagation anyway keeps it inert if sorting is ever enabled.
        onClick={(e): void => {
          e.stopPropagation();
          onChange(!showBestMatch);
        }}
        aria-pressed={showBestMatch}
        aria-label={t.cvModeAriaLabel}
        title={showBestMatch ? t.cvModeBestTooltip : t.cvModeActiveTooltip}
      >
        {showBestMatch ? t.cvModeBest : t.cvModeActive}
      </button>
    </span>
  );
}
