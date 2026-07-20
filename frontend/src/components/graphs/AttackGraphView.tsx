import { useMemo } from "react";
import { ReactFlow, Background, Controls, MiniMap, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { layoutGraph } from "./layout";
import type { ScanResult, CodeIntelligence } from "../../api/client";

const LAYER_STYLE: Record<string, { bg: string; border: string }> = {
  file: { bg: "rgba(57,135,229,0.18)", border: "#3987e5" },
  function: { bg: "rgba(144,133,233,0.16)", border: "#9085e9" },
  pointer: { bg: "rgba(213,81,129,0.16)", border: "#d55181" },
  api: { bg: "rgba(236,131,90,0.18)", border: "#ec835a" },
  cwe: { bg: "rgba(250,178,25,0.16)", border: "#fab219" },
  verdict: { bg: "rgba(208,59,59,0.2)", border: "#d03b3b" },
  safe: { bg: "rgba(12,163,12,0.18)", border: "#0ca30c" },
};

export default function AttackGraphView({ scan, intel }: { scan: ScanResult; intel: CodeIntelligence }) {
  const { laidNodes, laidEdges } = useMemo(() => {
    const nodes: any[] = [];
    const edges: any[] = [];
    let edgeId = 0;
    const addEdge = (source: string, target: string, color = "#52514e") => {
      edges.push({
        id: `e${edgeId++}`, source, target,
        style: { stroke: color },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
      });
    };
    const addNode = (id: string, label: string, layer: keyof typeof LAYER_STYLE, sub?: string) => {
      if (nodes.some((n) => n.id === id)) return;
      const style = LAYER_STYLE[layer];
      nodes.push({
        id, position: { x: 0, y: 0 }, width: 180, height: sub ? 52 : 40,
        data: { label: sub ? `${label}\n${sub}` : label },
        style: {
          background: style.bg, border: `1.5px solid ${style.border}`, borderRadius: 10,
          color: "#fff", fontSize: 11, fontFamily: "ui-monospace, monospace", padding: 6,
          width: 180, textAlign: "center", whiteSpace: "pre-line",
        },
      });
    };

    const fileId = "file";
    addNode(fileId, scan.filename, "file");

    intel.functions.forEach((f, fi) => {
      const fnId = `fn-${fi}`;
      addNode(fnId, `${f.name}()`, "function", `CC ${f.cyclomatic_complexity}`);
      addEdge(fileId, fnId, "#3987e5");

      const nPtr = f.pointer_ops ?? 0;
      if (nPtr > 0) {
        const ptrId = `ptr-${fi}`;
        addNode(ptrId, "Pointer Usage", "pointer", `${nPtr} operation(s)`);
        addEdge(fnId, ptrId, "#d55181");
      }

      f.dangerous_apis.forEach((api) => {
        const apiId = `api-${api}`;
        addNode(apiId, `${api}()`, "api", "dangerous API");
        addEdge(fnId, apiId, "#ec835a");

        const match = intel.dangerous_apis.find((d) => d.api === api);
        if (match?.cwe) {
          const cweId = `cwe-${match.cwe}`;
          addNode(cweId, match.cwe, "cwe", match.description ?? undefined);
          addEdge(apiId, cweId, "#fab219");
        }
      });
    });

    const verdictId = "verdict";
    const isVuln = scan.verdict === "VULNERABLE";
    addNode(verdictId, scan.verdict, isVuln ? "verdict" : "safe", `${scan.vuln_probability.toFixed(1)}% probability`);

    const cweNodes = nodes.filter((n) => n.id.startsWith("cwe-"));
    if (cweNodes.length > 0) {
      cweNodes.forEach((n) => addEdge(n.id, verdictId, isVuln ? "#d03b3b" : "#0ca30c"));
    } else {
      addEdge(fileId, verdictId, isVuln ? "#d03b3b" : "#0ca30c");
    }

    const { nodes: ln, edges: le } = layoutGraph(nodes, edges, "LR");
    return { laidNodes: ln, laidEdges: le };
  }, [scan, intel]);

  return (
    <div style={{ height: 520 }} className="rounded-lg overflow-hidden border border-(--border-hairline)">
      <ReactFlow nodes={laidNodes} edges={laidEdges} fitView proOptions={{ hideAttribution: true }} colorMode="dark" nodesDraggable nodesConnectable={false}>
        <Background color="#2c2c2a" gap={18} />
        <Controls showInteractive={false} />
        <MiniMap style={{ background: "#1a1a1f" }} maskColor="rgba(13,13,13,0.7)" />
      </ReactFlow>
    </div>
  );
}
