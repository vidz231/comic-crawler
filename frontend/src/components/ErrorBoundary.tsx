import { Component, type ReactNode, type ErrorInfo } from 'react';
import './ErrorBoundary.css';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional label shown in the error UI (e.g. "Browse", "Comic Detail"). */
  label?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catch rendering errors in a subtree so the rest of the app keeps working.
 * Shows a user-friendly error screen with a "Try again" button.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="error-boundary">
        <div className="error-boundary__card glass">
          <span className="error-boundary__icon" aria-hidden="true">⚠️</span>
          <h2 className="error-boundary__title">
            Something went wrong{this.props.label ? ` in ${this.props.label}` : ''}
          </h2>
          <p className="error-boundary__message">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            className="error-boundary__btn"
            onClick={this.handleReset}
          >
            Try again
          </button>
        </div>
      </div>
    );
  }
}
