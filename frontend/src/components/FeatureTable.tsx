const TYPICAL_MAX: Record<string, number> = {
  n_functions: 3, n_loops: 8, n_if_statements: 15, n_assignments: 25, n_returns: 6,
  n_pointer_ops: 15, n_function_calls: 15, n_binary_ops: 25, max_depth: 20,
  n_total_nodes: 600, n_error_nodes: 3,
  loc: 100, function_count: 3, loop_count: 8, if_count: 15, return_count: 6,
  avg_line_length: 60, max_line_length: 120, comment_count: 15, total_lines: 130,
  blank_lines: 25, nesting_depth: 8, operator_count: 40, pointer_count: 30,
};

export default function FeatureTable({ features }: { features: Record<string, number> }) {
  return (
    <div className="space-y-2.5">
      {Object.entries(features).map(([key, value]) => {
        const max = TYPICAL_MAX[key] ?? Math.max(1, value);
        const pct = Math.min(100, (Math.abs(value) / max) * 100);
        return (
          <div key={key}>
            <div className="flex justify-between text-[11px] mb-1">
              <span className="text-(--text-muted) mono">{key}</span>
              <span className="font-semibold tabular text-(--text-primary)">{typeof value === "number" ? (Number.isInteger(value) ? value : value.toFixed(2)) : value}</span>
            </div>
            <div className="h-1.5 rounded-full bg-(--surface-3) overflow-hidden">
              <div className="h-full rounded-full bg-(--series-1)" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
