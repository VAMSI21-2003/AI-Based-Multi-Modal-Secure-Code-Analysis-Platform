import { diffLines } from "diff";
import { useMemo } from "react";

interface DiffRow { left: string | null; right: string | null; type: "same" | "removed" | "added"; leftNum: number | null; rightNum: number | null; }

function buildDiffRows(oldText: string, newText: string): DiffRow[] {
  const parts = diffLines(oldText, newText);
  const rows: DiffRow[] = [];
  let leftNum = 1, rightNum = 1;

  for (const part of parts) {
    let lines = part.value.split("\n");
    if (lines[lines.length - 1] === "") lines = lines.slice(0, -1);

    if (part.added) {
      for (const l of lines) rows.push({ left: null, right: l, type: "added", leftNum: null, rightNum: rightNum++ });
    } else if (part.removed) {
      for (const l of lines) rows.push({ left: l, right: null, type: "removed", leftNum: leftNum++, rightNum: null });
    } else {
      for (const l of lines) rows.push({ left: l, right: l, type: "same", leftNum: leftNum++, rightNum: rightNum++ });
    }
  }
  return rows;
}

const ROW_STYLE: Record<string, { bg: string; border: string }> = {
  same: { bg: "transparent", border: "transparent" },
  removed: { bg: "rgba(208,59,59,0.12)", border: "#d03b3b" },
  added: { bg: "rgba(12,163,12,0.12)", border: "#0ca30c" },
};

export default function DiffViewer({ original, modified }: { original: string; modified: string }) {
  const rows = useMemo(() => buildDiffRows(original, modified), [original, modified]);
  const added = rows.filter((r) => r.type === "added").length;
  const removed = rows.filter((r) => r.type === "removed").length;

  return (
    <div>
      <div className="flex items-center gap-4 text-xs mb-2 px-1">
        <span className="text-(--status-good)">+{added} added</span>
        <span className="text-(--status-critical)">-{removed} removed</span>
      </div>
      <div className="grid grid-cols-2 rounded-lg overflow-hidden border border-(--border-hairline) mono text-[12px]">
        <div className="border-r border-(--border-hairline)">
          <div className="px-3 py-1.5 bg-(--surface-3) text-[10px] uppercase tracking-wider text-(--status-critical) font-semibold">Original</div>
          {rows.map((r, i) => (
            <div key={i} className="flex" style={{ background: r.type === "same" ? undefined : ROW_STYLE[r.type === "added" ? "same" : r.type].bg, borderLeft: r.type === "removed" ? `2px solid ${ROW_STYLE.removed.border}` : "2px solid transparent" }}>
              <span className="w-9 shrink-0 text-right pr-2 text-(--text-muted) select-none">{r.leftNum ?? ""}</span>
              <span className="px-2 whitespace-pre-wrap break-all flex-1 text-(--text-secondary)">{r.left ?? ""}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="px-3 py-1.5 bg-(--surface-3) text-[10px] uppercase tracking-wider text-(--status-good) font-semibold">Fixed</div>
          {rows.map((r, i) => (
            <div key={i} className="flex" style={{ background: r.type === "same" ? undefined : ROW_STYLE[r.type === "removed" ? "same" : r.type].bg, borderLeft: r.type === "added" ? `2px solid ${ROW_STYLE.added.border}` : "2px solid transparent" }}>
              <span className="w-9 shrink-0 text-right pr-2 text-(--text-muted) select-none">{r.rightNum ?? ""}</span>
              <span className="px-2 whitespace-pre-wrap break-all flex-1 text-(--text-secondary)">{r.right ?? ""}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
