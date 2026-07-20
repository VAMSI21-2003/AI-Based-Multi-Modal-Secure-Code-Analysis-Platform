import dagre from "dagre";
import type { Node, Edge } from "@xyflow/react";

// dagre's network-simplex ranking runs synchronously on the main thread with
// no yielding. A real repository scan can produce several thousand nodes
// (functions, pointers, buffers, ...); laying all of them out directly can
// freeze the tab for minutes. This is a defensive backstop -- callers that
// can pick a more meaningful subset (e.g. by node kind/priority) should
// still pre-filter before calling this, but no caller should ever be able
// to hand dagre an unbounded graph.
const HARD_MAX_NODES = 500;

export function layoutGraph(nodes: Node[], edges: Edge[], direction: "TB" | "LR" = "TB") {
  let workingNodes = nodes;
  let truncated = false;
  if (workingNodes.length > HARD_MAX_NODES) {
    truncated = true;
    workingNodes = workingNodes.slice(0, HARD_MAX_NODES);
  }
  const keptIds = new Set(workingNodes.map((n) => n.id));
  const workingEdges = truncated ? edges.filter((e) => keptIds.has(e.source) && keptIds.has(e.target)) : edges;

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 60 });

  workingNodes.forEach((n) => g.setNode(n.id, { width: n.width ?? 180, height: n.height ?? 44 }));
  workingEdges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  const laidOut = workingNodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - (n.width ?? 180) / 2, y: pos.y - (n.height ?? 44) / 2 },
    };
  });

  return { nodes: laidOut, edges: workingEdges, truncated, totalNodes: nodes.length };
}
