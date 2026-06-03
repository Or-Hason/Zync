import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { en } from "@/i18n/en";
import styles from "./ResumeDataErrorBoundary.module.css";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/**
 * Error boundary wrapping parsed-data panels.
 * Catches unexpected null/undefined field access so a malformed payload
 * cannot crash the full Resume Manager page.
 *
 * Must be a class component — React has no hook-based error boundary API.
 */
export class ResumeDataErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_error: Error): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ResumeDataErrorBoundary caught:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className={styles.fallback} role="alert">
          <p className={styles.title}>{en.pages.resumeManager.errorBoundaryTitle}</p>
          <p className={styles.body}>{en.pages.resumeManager.errorBoundaryBody}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
