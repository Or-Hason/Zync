import { en } from "@/i18n/en";
import styles from "./DeleteResumeModal.module.css";

const d = en.pages.resumeManager.delete;

interface DeleteResumeModalProps {
  /** Display name of the resume being deleted. */
  versionName: string;
  /** Whether the resume is the active one (changes copy + warns about auto-scan). */
  isActive: boolean;
  /** Whether the delete request is in flight. */
  isDeleting: boolean;
  /** Confirm deletion. */
  onConfirm: () => void;
  /** Dismiss without deleting. */
  onCancel: () => void;
}

/**
 * Confirmation dialog shown before deleting a resume. When the target is the
 * active resume, the copy warns that background auto-scanning will be disabled.
 *
 * @returns The rendered delete-confirmation modal.
 */
export function DeleteResumeModal({
  versionName,
  isActive,
  isDeleting,
  onConfirm,
  onCancel,
}: DeleteResumeModalProps): React.JSX.Element {
  const title = isActive ? d.activeTitle : d.title;
  const body = isActive ? d.activeBody : d.body;

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-resume-title"
    >
      <div className={styles.modal}>
        <h2 id="delete-resume-title" className={styles.title}>{title}</h2>
        <p className={styles.resumeName}>{versionName}</p>
        <p className={styles.message}>{body}</p>

        <div className={styles.actions}>
          <button
            className={styles.buttonSecondary}
            onClick={onCancel}
            disabled={isDeleting}
            aria-label={en.common.cancel}
          >
            {en.common.cancel}
          </button>
          <button
            className={styles.buttonDanger}
            onClick={onConfirm}
            disabled={isDeleting}
            aria-busy={isDeleting}
            aria-label={isDeleting ? d.deleting : d.confirm}
          >
            {isDeleting ? d.deleting : d.confirm}
          </button>
        </div>
      </div>
    </div>
  );
}
