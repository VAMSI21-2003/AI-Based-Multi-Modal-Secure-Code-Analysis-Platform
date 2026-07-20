import { useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { getScan, getScanDetail, type ScanResult, type ScanDetail } from "../api/client";

export function useActiveScan() {
  const [params] = useSearchParams();
  const scanId = params.get("scan");

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) {
      setScan(null);
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getScan(scanId), getScanDetail(scanId)])
      .then(([s, d]) => {
        if (cancelled) return;
        setScan(s);
        setDetail(d);
      })
      .catch((e) => { if (!cancelled) setError(e?.response?.data?.detail || e.message || "Failed to load scan"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scanId]);

  return { scanId, scan, detail, loading, error };
}
