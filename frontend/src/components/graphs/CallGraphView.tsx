import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Search } from "lucide-react";
import { layoutGraph } from "./layout";
import type { GraphNode, GraphEdge } from "../../api/client";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  recursiveNames?: string[];
  deadCodeNames?: string[];
  criticalNames?: string[];
  searchable?: boolean;
}

export default function CallGraphView({ nodes, edges, recursiveNames = [], deadCodeNames = [], criticalNames = [], searchable = false }: Props) {
  const [query, setQuery] = useState("");
  const recursiveSet = new Set(recursiveNames);
  const deadSet = new Set(deadCodeNames);
  const criticalSet = new Set(criticalNames);
  const q = query.trim().toLowerCase();

  const { laidNodes, laidEdges } = useMemo(() => {
    const rfNodes = nodes.map((n) => {
      const isDead = deadSet.has(n.id);
      const isCritical = criticalSet.has(n.id);
      const isRecursive = recursiveSet.has(n.id);
      const matches = !q || n.id.toLowerCase().includes(q);

      let border = n.type === "internal" ? "#3987e5" : "#9085e9";
      let bg = n.type === "internal" ? "rgba(57,135,229,0.16)" : "rgba(144,133,233,0.14)";
      if (isCritical) { border = "#d03b3b"; bg = "rgba(208,59,59,0.18)"; }
      else if (isDead) { border = "#898781"; bg = "rgba(137,135,129,0.12)"; }

      return {
        id: n.id,
        data: { label: n.label + (isRecursive ? " ↻" : "") + (isDead ? " (uncalled)" : "") },
        position: { x: 0, y: 0 },
        width: 150,
        height: 40,
        style: {
          background: bg,
          border: `${isCritical ? 2.5 : 1.5}px solid ${border}`,
          borderRadius: 8,
          color: "#fff",
          fontSize: 12,
          fontFamily: "ui-monospace, monospace",
          padding: 6,
          width: 150,
          textAlign: "center" as const,
          opacity: matches ? 1 : 0.25,
          boxShadow: isCritical ? "0 0 14px rgba(208,59,59,0.5)" : undefined,
        },
      };
    });
    const rfEdges = edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      animated: false,
      style: { stroke: "#52514e", opacity: !q || e.source.toLowerCase().includes(q) || e.target.toLowerCase().includes(q) ? 1 : 0.15 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#52514e", width: 16, height: 16 },
    }));
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "LR");
    return { laidNodes: ln, laidEdges: le };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, q, deadCodeNames.join(","), criticalNames.join(","), recursiveNames.join(",")]);

  if (nodes.length === 0) {
    return <div className="h-[320px] flex items-center justify-center text-sm text-(--text-muted)">No function calls detected.</div>;
  }

  return (
    <div className="rounded-lg overflow-hidden border border-(--border-hairline)">
      {searchable && (
        <div className="relative px-3 py-2 border-b border-(--border-hairline) bg-(--surface-2)">
          <Search size={12} className="absolute left-5 top-1/2 -translate-y-1/2 text-(--text-muted)" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search node names to highlight..."
            className="w-full bg-(--surface-3) border border-(--border-hairline) rounded-md pl-7 pr-3 py-1.5 text-xs focus-ring outline-none"
          />
        </div>
      )}
      <div style={{ height: 380 }}>
        <ReactFlow
          nodes={laidNodes}
          edges={laidEdges}
          fitView
          proOptions={{ hideAttribution: true }}
          colorMode="dark"
          nodesDraggable
          nodesConnectable={false}
          elementsSelectable
        >
          <Background color="#2c2c2a" gap={18} />
          <Controls showInteractive={false} />
          <MiniMap
            style={{ background: "#1a1a1f" }}
            maskColor="rgba(13,13,13,0.7)"
            nodeColor={(n: any) => (n.style?.border?.includes("3987e5") ? "#3987e5" : "#9085e9")}
          />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[11px] text-(--text-muted) px-3 py-2 border-t border-(--border-hairline) bg-(--surface-2)">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border border-(--series-1)" style={{ background: "rgba(57,135,229,0.3)" }} /> Function defined in file</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border border-(--series-7)" style={{ background: "rgba(144,133,233,0.3)" }} /> External / library call</span>
        {criticalNames.length > 0 && <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border-2 border-(--status-critical)" /> Critical (dangerous API / high complexity)</span>}
        {deadCodeNames.length > 0 && <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm border" style={{ borderColor: "#898781" }} /> Not called elsewhere in this file</span>}
        {recursiveNames.length > 0 && <span>↻ recursive</span>}
      </div>
    </div>
  );
}
