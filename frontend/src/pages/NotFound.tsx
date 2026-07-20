import { Link } from "react-router-dom";
import { ShieldAlert, Home, ScanLine } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-(--surface-2) border border-(--border-hairline) flex items-center justify-center mb-6">
          <ShieldAlert size={28} className="text-(--status-warning)" />
        </div>
        <div className="text-5xl font-bold tabular text-(--text-primary)">404</div>
        <p className="text-sm text-(--text-secondary) mt-3">
          This page doesn't exist, or the scan it points to may have been removed.
        </p>
        <div className="flex items-center justify-center gap-3 mt-6">
          <Link to="/" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--accent) text-white text-sm font-semibold hover:brightness-110">
            <Home size={14} /> Dashboard
          </Link>
          <Link to="/scanner" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-(--surface-2) border border-(--border-hairline) text-sm font-semibold hover:bg-(--surface-3)">
            <ScanLine size={14} /> Code Scanner
          </Link>
        </div>
      </div>
    </div>
  );
}
