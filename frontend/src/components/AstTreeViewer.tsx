import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface AstNode {
  type: string;
  start: number;
  end: number;
  text: string;
  children: AstNode[];
  isError: boolean;
}

function Node({ node, depth }: { node: AstNode; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        onClick={() => hasChildren && setOpen((o) => !o)}
        className={`flex items-center gap-1 py-0.5 rounded cursor-pointer hover:bg-(--surface-3) text-xs ${node.isError ? "text-(--status-critical)" : ""}`}
        style={{ paddingLeft: depth * 14 }}
      >
        {hasChildren ? (open ? <ChevronDown size={11} className="shrink-0 text-(--text-muted)" /> : <ChevronRight size={11} className="shrink-0 text-(--text-muted)" />) : <span className="w-[11px] shrink-0" />}
        <span className="mono font-medium text-(--series-1)">{node.type}</span>
        {!hasChildren && node.text && <span className="mono text-(--text-muted) truncate">"{node.text}"</span>}
        <span className="text-(--text-muted) text-[10px] ml-auto shrink-0">L{node.start}</span>
      </div>
      {open && hasChildren && (
        <div>
          {node.children.map((c, i) => <Node key={i} node={c} depth={depth + 1} />)}
        </div>
      )}
    </div>
  );
}

export default function AstTreeViewer({ tree, available, error }: { tree: AstNode | null; available: boolean; error?: string }) {
  if (!available || !tree) {
    return <div className="text-xs text-(--text-muted) py-6 text-center">AST unavailable{error ? `: ${error}` : " (tree-sitter parse failed)"}.</div>;
  }
  return (
    <div className="max-h-[380px] overflow-y-auto scrollbar-thin">
      <Node node={tree} depth={0} />
    </div>
  );
}
