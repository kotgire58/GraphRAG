import { useRef, useCallback, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphData } from "../types";

const LABEL_COLORS: Record<string, string> = {
  Patient: "#10b981",
  Drug: "#6366f1",
  Enzyme: "#f59e0b",
  Transporter: "#06b6d4",
  Condition: "#ef4444",
  Physician: "#3b82f6",
  Hospital: "#8b5cf6",
  Manufacturer: "#64748b",
  Protocol: "#84cc16",
};

interface GraphVizProps {
  data: GraphData;
  onNodeClick?: (name: string) => void;
  width?: number;
  height?: number;
}

export default function GraphViz({
  data,
  onNodeClick,
  width = 300,
  height = 240,
}: GraphVizProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);

  useEffect(() => {
    if (fgRef.current?.d3ReheatSimulation) fgRef.current.d3ReheatSimulation();
  }, [data]);

  const handleClick = useCallback(
    (node: { name?: string }) => {
      if (node.name && onNodeClick) onNodeClick(node.name);
    },
    [onNodeClick]
  );

  const nodeCanvasObject = useCallback(
    (
      node: { x?: number; y?: number; name?: string; label?: string },
      ctx: CanvasRenderingContext2D,
    ) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const label = node.name ?? "?";
      const color = LABEL_COLORS[node.label ?? ""] ?? "#6366f1";
      const radius = 5;

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      ctx.font = "3px sans-serif";
      ctx.fillStyle = "#cbd5e1";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(label, x, y + radius + 1);
    },
    []
  );

  const linkCanvasObject = useCallback(
    (
      link: {
        source?: { x?: number; y?: number };
        target?: { x?: number; y?: number };
        type?: string;
      },
      ctx: CanvasRenderingContext2D,
    ) => {
      const src = link.source as { x?: number; y?: number } | undefined;
      const tgt = link.target as { x?: number; y?: number } | undefined;
      if (src?.x == null || src?.y == null || tgt?.x == null || tgt?.y == null) {
        return;
      }
      ctx.beginPath();
      ctx.moveTo(src.x, src.y);
      ctx.lineTo(tgt.x, tgt.y);
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 0.6;
      ctx.stroke();

      const midX = (src.x + tgt.x) / 2;
      const midY = (src.y + tgt.y) / 2;
      const relLabel = link.type ?? "";
      if (relLabel) {
        ctx.font = "2px sans-serif";
        ctx.fillStyle = "#94a3b8";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(relLabel, midX, midY);
      }
    },
    [],
  );

  if (data.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs">
        Run a graph query to see the traversal
      </div>
    );
  }

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={data}
      nodeId="id"
      width={width}
      height={height}
      backgroundColor="#0f172a"
      nodeCanvasObject={nodeCanvasObject}
      linkCanvasObject={linkCanvasObject}
      linkColor={() => "#475569"}
      linkWidth={0.6}
      linkDirectionalArrowLength={3}
      linkDirectionalArrowRelPos={1}
      onNodeClick={handleClick}
      cooldownTicks={60}
    />
  );
}
