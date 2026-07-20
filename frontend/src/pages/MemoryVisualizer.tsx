import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Layers, Box, ArrowRightLeft, AlertTriangle, MemoryStick } from "lucide-react";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import { Spinner } from "../components/Loading";
import ScanPickerEmpty from "../components/ScanPickerEmpty";
import { useActiveScan } from "../hooks/useActiveScan";
import { getCodeIntelligence, type CodeIntelligence } from "../api/client";

export default function MemoryVisualizer() {
  const { scanId, scan, loading } = useActiveScan();
  const [intel, setIntel] = useState<CodeIntelligence | null>(null);

  useEffect(() => { if (scanId) getCodeIntelligence(scanId).then(setIntel); }, [scanId]);

  if (!scanId) {
    return (
      <PageShell title="Memory Visualizer" subtitle="Stack, heap, pointers, allocation & leaks — from the actual scanned code">
        <ScanPickerEmpty icon={MemoryStick} title="No scan selected" description="Run a scan to visualise its real memory allocation, stack buffers, and pointer usage." />
      </PageShell>
    );
  }

  if (loading || !scan || !intel) {
    return <PageShell title="Memory Visualizer" subtitle="Loading"><Spinner label="Tracing memory operations..." /></PageShell>;
  }

  const { memory, pointers } = intel;
  const events = [
    ...memory.alloc_sites.map((a) => ({ ...a, kind: "alloc" as const })),
    ...memory.free_sites.map((f) => ({ ...f, kind: "free" as const, api: "free" })),
  ].sort((a, b) => a.line - b.line);

  return (
    <PageShell title="Memory Visualizer" subtitle={`${scan.filename} — real allocation trace from this scan`}>
      {(memory.potential_leak || memory.potential_double_free_risk) && (
        <div className="card p-4 mb-5 border-(--status-critical) flex items-center gap-3">
          <AlertTriangle className="text-(--status-critical)" size={20} />
          <div className="text-sm text-(--status-critical)">
            {memory.potential_leak && `Allocation/free imbalance: ${memory.balance} block(s) allocated but never freed on this path. `}
            {memory.potential_double_free_risk && "More frees than allocations detected -- check for double-free."}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <ChartCard title="Stack" subtitle={<span className="flex items-center gap-1.5"><Layers size={12} /> Fixed-size local buffers</span>}>
          <div className="space-y-2">
            {memory.stack_buffers.length === 0 && <div className="text-xs text-(--text-muted)">No fixed-size stack buffers detected.</div>}
            {memory.stack_buffers.map((b, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }}
                className="rounded-lg px-3 py-2.5 text-xs mono" style={{ background: "rgba(57,135,229,0.14)", border: "1.5px solid #3987e5" }}>
                {b.name}[{b.size}] <span className="float-right text-(--text-muted)">L{b.line}</span>
              </motion.div>
            ))}
          </div>
          <div className="mt-3 text-[11px] text-(--text-muted)">Estimated stack usage: {memory.stack_bytes_estimate} bytes</div>
        </ChartCard>

        <ChartCard title="Heap" subtitle={<span className="flex items-center gap-1.5"><Box size={12} /> Allocation / free timeline</span>}>
          <div className="space-y-2">
            {events.length === 0 && <div className="text-xs text-(--text-muted)">No dynamic memory allocation detected.</div>}
            {events.map((e, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                className="rounded-lg px-3 py-2.5 text-xs mono flex items-center justify-between"
                style={{
                  background: e.kind === "alloc" ? "rgba(12,163,12,0.14)" : "rgba(137,135,129,0.14)",
                  border: `1.5px solid ${e.kind === "alloc" ? "#0ca30c" : "#898781"}`,
                }}>
                <span>{e.kind === "alloc" ? (e as any).api + "()" : "free()"}</span>
                <span className="text-(--text-muted)">L{e.line}</span>
              </motion.div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 mt-3 text-[11px]">
            <div className="text-(--status-good)">{memory.allocations} allocation(s)</div>
            <div className="text-(--text-muted) text-right">{memory.frees} free(s)</div>
          </div>
        </ChartCard>

        <ChartCard title="Pointers" subtitle={<span className="flex items-center gap-1.5"><ArrowRightLeft size={12} /> Usage & safety coverage</span>}>
          <div className="space-y-2.5">
            <Row label="Pointer Variables" value={pointers.pointer_variables} />
            <Row label="Dereferences" value={pointers.dereferences} />
            <Row label="Double Pointers" value={pointers.double_pointers} />
            <Row label="NULL Checks" value={pointers.null_checks} />
          </div>
          <div className="mt-4">
            <div className="flex justify-between text-[11px] mb-1"><span className="text-(--text-muted)">Null-check coverage</span><span>{pointers.null_check_coverage_pct}%</span></div>
            <div className="h-1.5 rounded-full bg-(--surface-3) overflow-hidden"><div className="h-full bg-(--series-1) rounded-full" style={{ width: `${Math.min(100, pointers.null_check_coverage_pct)}%` }} /></div>
          </div>
        </ChartCard>
      </div>

      <ChartCard title="Variable Declarations" subtitle="Locals, parameters, and mutation frequency">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Row label="Declared" value={intel.variables.total_declared} />
          <Row label="Parameters" value={intel.variables.parameters} />
          <Row label="Locals" value={intel.variables.locals} />
          <Row label="Most Mutated" value={intel.variables.most_mutated[0]?.name ?? "-"} />
        </div>
      </ChartCard>
    </PageShell>
  );
}

function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-(--surface-3) rounded-lg p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-(--text-muted)">{label}</div>
      <div className="text-sm font-bold mt-0.5">{value}</div>
    </div>
  );
}
