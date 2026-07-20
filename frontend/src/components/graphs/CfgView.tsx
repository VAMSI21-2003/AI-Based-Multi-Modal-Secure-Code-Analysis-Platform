import { useMemo } from "react";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { layoutGraph } from "./layout";
import type { GraphNode, GraphEdge } from "../../api/client";

const KIND_STYLE: Record<string, { bg: string; border: string; shape?: string }> = {
  entry: { bg: "rgba(12,163,12,0.18)", border: "#0ca30c" },
  exit: { bg: "rgba(208,59,59,0.18)", border: "#d03b3b" },
  branch: { bg: "rgba(250,178,25,0.16)", border: "#fab219" },
  loop: { bg: "rgba(144,133,233,0.18)", border: "#9085e9" },
  return: { bg: "rgba(57,135,229,0.16)", border: "#3987e5" },
  break: { bg: "rgba(236,131,90,0.16)", border: "#ec835a" },
  continue: { bg: "rgba(236,131,90,0.16)", border: "#ec835a" },
  block: { bg: "#212227", border: "#383835" },
};

const EDGE_COLOR: Record<string, string> = {
  true: "#0ca30c", false: "#d03b3b", loop: "#9085e9", "back-edge": "#c98500", continue: "#ec835a",
};

export default function CfgView({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const { laidNodes, laidEdges } = useMemo(() => {
    const rfNodes = nodes.map((n) => {
      const style = KIND_STYLE[n.kind ?? "block"] ?? KIND_STYLE.block;
      const isWide = n.kind === "block";
      return {
        id: n.id,
        data: { label: n.label + (n.line ? `  (L${n.line})` : "") },
        position: { x: 0, y: 0 },
        width: isWide ? 260 : 170,
        height: 44,
        style: {
          background: style.bg,
          border: `1.5px solid ${style.border}`,
          borderRadius: n.kind === "branch" ? 4 : 10,
          color: "#fff",
          fontSize: 11,
          fontFamily: "ui-monospace, monospace",
          padding: 6,
          width: isWide ? 260 : 170,
          textAlign: "center" as const,
        },
      };
    });
    const rfEdges = edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      label: e.label ?? undefined,
      labelStyle: { fill: EDGE_COLOR[e.label ?? ""] ?? "#898781", fontSize: 10 },
      style: { stroke: EDGE_COLOR[e.label ?? ""] ?? "#52514e", strokeDasharray: e.label === "back-edge" ? "4 3" : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLOR[e.label ?? ""] ?? "#52514e", width: 14, height: 14 },
    }));
    const { nodes: ln, edges: le } = layoutGraph(rfNodes, rfEdges, "TB");
    return { laidNodes: ln, laidEdges: le };
  }, [nodes, edges]);

  if (nodes.length === 0) {
    return <div className="h-[320px] flex items-center justify-center text-sm text-(--text-muted)">No function body to visualise.</div>;
  }

  return (
    <div style={{ height: 460 }} className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <ReactFlow
        nodes={laidNodes}
        edges={laidEdges}
        fitView
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
        nodesDraggable
        nodesConnectable={false}
      >
        <Background color="#2c2c2a" gap={18} />
        <Controls showInteractive={false} />
        <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
      </ReactFlow>
    </div>
  );
}
