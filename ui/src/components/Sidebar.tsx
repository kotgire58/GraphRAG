import { useEffect, useState, useCallback } from "react";
import {
  Brain,
  Database,
  Zap,
  Search,
  Network,
  Bot,
  Trash2,
} from "lucide-react";
import axios from "axios";
import type { HealthStatus, Mode } from "../types";
import { apiUrl } from "../api";
import { useStore } from "../store";

const MODES: { key: Mode; label: string; icon: typeof Search }[] = [
  { key: "vector", label: "Vector RAG", icon: Search },
  { key: "graph", label: "Graph RAG", icon: Network },
  { key: "agentic", label: "Agentic", icon: Bot },
];

const DEMO_QUERIES = [
  "Is Fluconazole safe for PT-005?",
  "Is Fluconazole safe for PT-001?",
  "PT-004 is being treated for a fungal infection. Their doctor wants to prescribe Fluconazole. PT-004 is also scheduled for a CT scan with IV contrast next week. Is it safe to proceed with both the Fluconazole and the contrast procedure given PT-004's current medications, and what specific monitoring protocol should be followed?",
  "Warfarin + Amiodarone + Digoxin + Fluconazole?",
  "What does CYP3A4 metabolize?",
  "Which drugs interact with P-glycoprotein?",
];

interface SidebarProps {
  onSubmitQuery: (q: string) => void;
}

export default function Sidebar({ onSubmitQuery }: SidebarProps) {
  const { mode, setMode, stats, clearMessages } = useStore();
  const [health, setHealth] = useState<HealthStatus | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const { data } = await axios.get<HealthStatus>(apiUrl("/health"));
      setHealth(data);
    } catch {
      setHealth({ postgres: "error", neo4j: "error", llm: "error" });
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 30_000);
    return () => clearInterval(id);
  }, [checkHealth]);

  const isConnected =
    health?.postgres === "ok" && health?.neo4j === "ok";

  const sortedLabels = stats
    ? Object.entries(stats.nodes_by_label)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
    : [];

  return (
    <aside className="w-60 bg-[#0f172a] border-r border-slate-700/50 flex flex-col h-full shrink-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <Brain className="text-indigo-400" size={22} />
          <h1 className="font-bold text-lg text-white tracking-tight">
            GraphRAG <span className="text-indigo-400 text-sm font-normal">PoC</span>
          </h1>
        </div>
      </div>

      {/* Health */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" : "bg-red-400"}`}
          />
          <span className="text-slate-300">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Graph Stats */}
      {stats && (
        <div className="px-4 py-3 border-b border-slate-700/50">
          <h2 className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-semibold">
            Graph Stats
          </h2>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1">
                <Database size={11} className="text-slate-500" />
                Nodes
              </span>
              <span className="font-mono text-white">
                {stats.total_nodes.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between text-slate-300">
              <span className="flex items-center gap-1">
                <Zap size={11} className="text-slate-500" />
                Relationships
              </span>
              <span className="font-mono text-white">
                {stats.total_relationships.toLocaleString()}
              </span>
            </div>
          </div>
          {sortedLabels.length > 0 && (
            <div className="mt-2 space-y-0.5">
              {sortedLabels.map(([label, count]) => (
                <div
                  key={label}
                  className="flex justify-between text-[11px] text-slate-400"
                >
                  <span>{label}</span>
                  <span className="font-mono text-slate-500">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Mode selector */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        <h2 className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-semibold">
          Mode
        </h2>
        <div className="flex flex-col gap-1">
          {MODES.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setMode(key)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors cursor-pointer ${
                mode === key
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Demo Queries */}
      <div className="px-4 py-3 flex-1 overflow-y-auto">
        <h2 className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-semibold">
          Demo Queries
        </h2>
        <div className="flex flex-col gap-1.5">
          {DEMO_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => onSubmitQuery(q)}
              className="text-left text-xs text-slate-400 hover:text-indigo-300 hover:bg-slate-800/50 rounded px-2 py-1.5 transition-colors cursor-pointer leading-tight"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Clear */}
      <div className="px-4 py-3 border-t border-slate-700/50">
        <button
          onClick={clearMessages}
          className="flex items-center gap-2 text-xs text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
        >
          <Trash2 size={12} />
          Clear chat
        </button>
      </div>
    </aside>
  );
}
