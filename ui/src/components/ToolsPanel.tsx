import { Search, Network, ChevronDown, ChevronUp, ArrowRight, Info } from "lucide-react";
import { useState } from "react";
import type { Message, SeedFactItem } from "../types";
import { useStore } from "../store";
import { useGraph } from "../hooks/useGraph";
import TraversalPath from "./TraversalPath";
import GraphViz from "./GraphViz";

const NODE_COLORS: Record<string, string> = {
  Patient: "bg-emerald-600",
  Drug: "bg-indigo-600",
  Enzyme: "bg-amber-600",
  Transporter: "bg-cyan-600",
  Condition: "bg-red-600",
  Physician: "bg-blue-600",
  Hospital: "bg-purple-600",
  Manufacturer: "bg-slate-600",
  Protocol: "bg-lime-600",
};

const NODE_BORDER_COLORS: Record<string, string> = {
  Patient: "border-emerald-500",
  Drug: "border-indigo-500",
  Enzyme: "border-amber-500",
  Transporter: "border-cyan-500",
  Condition: "border-red-500",
  Physician: "border-blue-500",
  Hospital: "border-purple-500",
  Manufacturer: "border-slate-500",
  Protocol: "border-lime-500",
};

const NODE_TEXT_COLORS: Record<string, string> = {
  Patient: "text-emerald-100",
  Drug: "text-indigo-100",
  Enzyme: "text-amber-100",
  Transporter: "text-cyan-100",
  Condition: "text-red-100",
  Physician: "text-blue-100",
  Hospital: "text-purple-100",
  Manufacturer: "text-slate-100",
  Protocol: "text-lime-100",
};

const LABEL_HEURISTICS: [string, string][] = [
  ["PT-", "Patient"],
  ["CYP", "Enzyme"],
  ["P-glycoprotein", "Transporter"],
  ["OCT2", "Transporter"],
  ["MATE", "Transporter"],
  ["Dr.", "Physician"],
  ["Metro", "Hospital"],
  ["Diabetes", "Condition"],
  ["Hypertension", "Condition"],
  ["QT Prolongation", "Condition"],
  ["Torsades", "Condition"],
  ["Bleeding", "Condition"],
  ["Rhabdomyolysis", "Condition"],
  ["Nephrotoxicity", "Condition"],
  ["Hypoglycemia", "Condition"],
  ["Hepatic Impairment", "Condition"],
];

function guessNodeLabel(
  name: string,
  seedFacts?: SeedFactItem[] | null,
): string {
  if (seedFacts) {
    for (const sf of seedFacts) {
      const extra = sf as SeedFactItem & { from_label?: string; to_label?: string };
      if (extra.from_name === name && extra.from_label) return extra.from_label;
      if (extra.to_name === name && extra.to_label) return extra.to_label;
    }
  }
  for (const [prefix, label] of LABEL_HEURISTICS) {
    if (name.startsWith(prefix) || name.includes(prefix)) return label;
  }
  return "Drug";
}

interface CriticalPathNode {
  name: string;
  label: string;
}

interface CriticalPathEdge {
  relType: string;
}

function parseCriticalPath(
  raw: string,
  seedFacts?: SeedFactItem[] | null,
): { nodes: CriticalPathNode[]; edges: CriticalPathEdge[] } {
  const nodes: CriticalPathNode[] = [];
  const edges: CriticalPathEdge[] = [];

  const parts = raw.split(/\s*-\[/);
  for (let i = 0; i < parts.length; i++) {
    if (i === 0) {
      const name = parts[i].trim();
      if (name) {
        nodes.push({ name, label: guessNodeLabel(name, seedFacts) });
      }
      continue;
    }
    const [relPart, rest] = parts[i].split(/\]->\s*/);
    if (relPart) {
      edges.push({ relType: relPart.replace(/\{.*\}/, "").trim() });
    }
    if (rest) {
      const name = rest.trim();
      if (name) {
        nodes.push({ name, label: guessNodeLabel(name, seedFacts) });
      }
    }
  }

  return { nodes, edges };
}

function SourceCard({ source, idx }: { source: { content?: string; filename?: string; similarity?: number; fact?: string }; idx: number }) {
  const { filename, content, similarity, fact } = source;

  if (fact) {
    return (
      <div className="text-xs text-slate-400 py-1 border-b border-slate-700/30 last:border-0">
        <span className="font-mono text-slate-500 mr-1">{idx + 1}.</span>
        {fact}
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 rounded p-2 text-xs">
      {filename && (
        <span className="inline-block bg-indigo-500/20 text-indigo-300 rounded px-1.5 py-0.5 text-[10px] font-medium mb-1">
          {filename}
        </span>
      )}
      {content && (
        <p className="text-slate-400 leading-relaxed line-clamp-3">
          {content.slice(0, 150)}
          {content.length > 150 ? "..." : ""}
        </p>
      )}
      {similarity != null && (
        <span className="text-[10px] text-slate-500 mt-1 inline-block">
          Similarity: {(similarity * 100).toFixed(1)}%
        </span>
      )}
    </div>
  );
}

export default function ToolsPanel() {
  const lastResponse = useStore((s) => s.lastResponse);
  const graphData = useStore((s) => s.graphData);
  const { fetchNode } = useGraph();
  const [graphExpanded, setGraphExpanded] = useState(true);
  const [howExpanded, setHowExpanded] = useState(false);

  if (!lastResponse) {
    return (
      <aside className="w-80 bg-[#0b1120] border-l border-slate-700/50 flex flex-col h-full shrink-0">
        <div className="flex-1 flex items-center justify-center text-slate-600 text-sm px-6 text-center">
          Ask a question to see retrieval details here
        </div>
      </aside>
    );
  }

  const msg: Message = lastResponse;
  const isVector = msg.mode === "vector";
  const isGraph = msg.mode === "graph";
  const isGraphLike = isGraph || msg.mode === "agentic";
  const tools = msg.tools_used ?? [];
  const sources = msg.sources ?? [];
  const paths = msg.traversal_path ?? [];
  const te = msg.traversal_explanation;
  const criticalPath = te?.critical_path ?? "";
  const criticalParsed = criticalPath
    ? parseCriticalPath(criticalPath, msg.seed_facts)
    : null;

  return (
    <aside className="w-80 bg-[#0b1120] border-l border-slate-700/50 flex flex-col h-full shrink-0 overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        <h2 className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-2">
          Tools Used
        </h2>
        <div className="flex flex-wrap gap-1.5">
          {tools.map((t) => (
            <span
              key={t}
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${
                t.includes("vector")
                  ? "bg-blue-500/15 text-blue-300 border border-blue-500/30"
                  : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              }`}
            >
              {t.includes("vector") ? (
                <Search size={10} />
              ) : (
                <Network size={10} />
              )}
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Sources */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        {isVector && (
          <>
            <h3 className="text-xs font-semibold text-slate-300 mb-2">
              Chunks Retrieved:{" "}
              <span className="text-indigo-400">{sources.length}</span>
            </h3>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {sources.map((s, i) => (
                <SourceCard key={i} source={s} idx={i} />
              ))}
            </div>
          </>
        )}
        {(isGraph || msg.mode === "agentic") && (
          <>
            <h3 className="text-xs font-semibold text-slate-300 mb-2">
              Facts Retrieved:{" "}
              <span className="text-emerald-400">{sources.length}</span>
            </h3>
            {paths.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">
                  Traversal Paths
                </h4>
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {paths.map((p, i) => (
                    <div
                      key={i}
                      className="bg-slate-800/40 rounded p-2 border border-slate-700/30"
                    >
                      <TraversalPath path={p} compact />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {sources.length > 0 && paths.length === 0 && (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {sources.slice(0, 20).map((s, i) => (
                  <SourceCard key={i} source={s} idx={i} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Critical Path */}
      {isGraphLike && criticalParsed && criticalParsed.nodes.length >= 2 && (
        <div className="px-4 py-3 border-b border-slate-700/50">
          <h4 className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-3">
            Critical Path
          </h4>
          <div className="overflow-x-auto pb-1">
            <div className="flex items-center gap-0 min-w-max">
              {criticalParsed.nodes.map((node, i) => {
                const bg = NODE_COLORS[node.label] ?? "bg-slate-600";
                const border = NODE_BORDER_COLORS[node.label] ?? "border-slate-500";
                const text = NODE_TEXT_COLORS[node.label] ?? "text-slate-100";
                const edge = criticalParsed.edges[i];
                return (
                  <div key={i} className="flex items-center">
                    <div className="flex flex-col items-center">
                      <span
                        className={`${bg} ${text} ${border} border rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap`}
                      >
                        {node.name}
                      </span>
                      <span className="text-[9px] text-slate-500 mt-0.5">
                        {node.label}
                      </span>
                    </div>
                    {edge && (
                      <div className="flex flex-col items-center mx-1">
                        <span className="text-[9px] text-slate-500 font-mono mb-0.5 whitespace-nowrap">
                          {edge.relType}
                        </span>
                        <div className="flex items-center">
                          <div className="w-6 h-px bg-slate-600" />
                          <ArrowRight size={10} className="text-slate-500 -ml-1" />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* How It Works */}
      {isGraphLike && te && (
        <div className="px-4 py-3 border-b border-slate-700/50">
          <button
            onClick={() => setHowExpanded(!howExpanded)}
            className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-slate-500 font-semibold cursor-pointer hover:text-slate-300 transition-colors w-full"
          >
            <Info size={11} />
            How It Works
            {howExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {howExpanded && (
            <div className="mt-2 space-y-2">
              {te.entities_identified && te.entities_identified.length > 0 && (
                <div>
                  <span className="text-[10px] text-slate-500">
                    Entities identified:
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {te.entities_identified.map((ent) => (
                      <span
                        key={ent}
                        className="inline-block bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 rounded px-1.5 py-0.5 text-[10px] font-medium"
                      >
                        {ent}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {te.total_facts_in_context != null && (
                <div className="text-[10px] text-slate-500">
                  Facts in context:{" "}
                  <span className="text-emerald-400 font-medium">
                    {te.total_facts_in_context}
                  </span>
                </div>
              )}
              {te.how_it_works && (
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {te.how_it_works}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Graph visualization */}
      <div className="px-4 py-3 flex-1 min-h-0">
        <button
          onClick={() => setGraphExpanded(!graphExpanded)}
          className="flex items-center gap-1 text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-2 cursor-pointer hover:text-slate-300 transition-colors w-full"
        >
          Traversal Graph
          {graphExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {graphExpanded && (
          <div className="rounded border border-slate-700/30 overflow-hidden bg-[#0f172a]">
            <GraphViz
              data={graphData}
              onNodeClick={fetchNode}
              width={280}
              height={220}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
