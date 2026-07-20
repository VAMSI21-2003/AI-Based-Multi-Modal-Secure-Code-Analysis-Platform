import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("SecureCode AI crashed:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center px-6">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-(--status-critical)/15 border border-(--status-critical)/40 flex items-center justify-center mb-6">
              <AlertTriangle size={28} className="text-(--status-critical)" />
            </div>
            <h1 className="text-xl font-bold">Something went wrong</h1>
            <p className="text-sm text-(--text-secondary) mt-2">
              This page hit an unexpected error. The rest of the platform is unaffected — try reloading this page.
            </p>
            <pre className="mono text-[11px] text-(--text-muted) bg-(--surface-2) rounded-lg p-3 mt-4 text-left overflow-x-auto max-h-32">{this.state.error.message}</pre>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload(); }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110 mt-5"
            >
              <RefreshCw size={14} /> Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
