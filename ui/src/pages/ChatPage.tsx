import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Search,
  Network,
  Bot,
  AlertTriangle,
  CheckCircle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { Mode, Message } from "../types";
import { useStore } from "../store";
import { useChat } from "../hooks/useChat";
import TraversalPath from "../components/TraversalPath";

const MODE_TABS: { key: Mode; label: string; icon: typeof Search }[] = [
  { key: "vector", label: "Vector RAG", icon: Search },
  { key: "graph", label: "Graph RAG", icon: Network },
  { key: "agentic", label: "Agentic", icon: Bot },
];

type Verdict = "DANGEROUS" | "CAUTION REQUIRED" | "SAFE" | null;

function parseVerdict(text: string): Verdict {
  const upper = text.toUpperCase();
  if (upper.includes("VERDICT: DANGEROUS") || upper.includes("VERDICT:DANGEROUS"))
    return "DANGEROUS";
  if (upper.includes("VERDICT: CAUTION REQUIRED") || upper.includes("VERDICT:CAUTION REQUIRED"))
    return "CAUTION REQUIRED";
  if (upper.includes("VERDICT: SAFE") || upper.includes("VERDICT:SAFE"))
    return "SAFE";
  return null;
}

function parseStructuredAnswer(raw: string) {
  const simpleMatch = raw.match(/###SIMPLE###([\s\S]*?)###END_SIMPLE###/);
  const detailedMatch = raw.match(/###DETAILED###([\s\S]*?)###END_DETAILED###/);
  const simpleText = simpleMatch ? simpleMatch[1].trim() : null;
  const detailedText = detailedMatch ? detailedMatch[1].trim() : null;
  return { simpleText, detailedText };
}

function stripVerdictLine(text: string): string {
  return text
    .split("\n")
    .filter((l) => !l.trim().toUpperCase().startsWith("VERDICT:"))
    .join("\n")
    .trim();
}

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  if (verdict === "DANGEROUS") {
    return (
      <span className="inline-flex items-center gap-1 bg-red-500/15 text-red-400 border border-red-500/30 rounded-full px-3 py-1 text-sm font-semibold mb-3">
        <AlertTriangle size={14} />
        DANGEROUS
      </span>
    );
  }
  if (verdict === "CAUTION REQUIRED") {
    return (
      <span className="inline-flex items-center gap-1 bg-amber-500/15 text-amber-400 border border-amber-500/30 rounded-full px-3 py-1 text-sm font-semibold mb-3">
        <ShieldAlert size={14} />
        CAUTION REQUIRED
      </span>
    );
  }
  if (verdict === "SAFE") {
    return (
      <span className="inline-flex items-center gap-1 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded-full px-3 py-1 text-sm font-semibold mb-3">
        <CheckCircle size={14} />
        SAFE
      </span>
    );
  }
  return null;
}

function ModeBadge({ mode }: { mode: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    vector: { bg: "bg-blue-500/15 border-blue-500/30", text: "text-blue-300", label: "Vector" },
    graph: { bg: "bg-emerald-500/15 border-emerald-500/30", text: "text-emerald-300", label: "Graph" },
    agentic: { bg: "bg-purple-500/15 border-purple-500/30", text: "text-purple-300", label: "Agentic" },
  };
  const c = config[mode] ?? config.agentic;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border ${c.bg} ${c.text}`}>
      {c.label}
    </span>
  );
}

function ChatBubble({ msg }: { msg: Message }) {
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const isUser = msg.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="bg-indigo-600 rounded-2xl rounded-br-sm px-4 py-2.5 max-w-[70%]">
          <p className="text-sm text-white whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    );
  }

  const paths = msg.traversal_path ?? [];
  const isGraph = msg.mode === "graph" || msg.mode === "agentic";

  const { simpleText, detailedText } = parseStructuredAnswer(msg.content);
  const isSafetyAnswer = simpleText !== null;

  const verdict: Verdict = isSafetyAnswer
    ? parseVerdict(simpleText)
    : parseVerdict(msg.content);

  const displayContent = isSafetyAnswer
    ? stripVerdictLine(simpleText)
    : msg.content;

  return (
    <div className="flex justify-start">
      <div className="bg-[#1e293b] rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] border border-slate-700/50">
        <div className="flex items-center gap-2 mb-2">
          <ModeBadge mode={msg.mode} />
        </div>
        <VerdictBadge verdict={verdict} />
        <div className="text-sm text-slate-200 leading-relaxed prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{displayContent}</ReactMarkdown>
        </div>
        {isSafetyAnswer && detailedText && (
          <div className="mt-2">
            <button
              onClick={() => setDetailsExpanded(!detailsExpanded)}
              className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer transition-colors"
            >
              {detailsExpanded ? "Hide detailed analysis" : "Show detailed analysis"}
              {detailsExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {detailsExpanded && (
              <div className="mt-2 bg-slate-800/70 rounded-lg px-3 py-2.5 border border-slate-700/40">
                <div className="text-sm text-slate-300 leading-relaxed prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{detailedText}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        )}
        {isGraph && paths.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700/50">
            <h4 className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold mb-2">
              Traversal Paths
            </h4>
            <div className="space-y-1.5">
              {paths.slice(0, 5).map((p, i) => (
                <TraversalPath key={i} path={p} compact />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-[#1e293b] rounded-2xl rounded-bl-sm px-4 py-3 border border-slate-700/50">
        <div className="flex gap-1.5">
          <span className="w-2 h-2 rounded-full bg-slate-500 animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 rounded-full bg-slate-500 animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 rounded-full bg-slate-500 animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

interface ChatPageProps {
  pendingQuery: string | null;
  clearPending: () => void;
}

export default function ChatPage({ pendingQuery, clearPending }: ChatPageProps) {
  const { mode, setMode } = useStore();
  const { sendMessage, messages, loading } = useChat();
  const [input, setInput] = useState("");
  const messagesEnd = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(scrollToBottom, [messages, loading, scrollToBottom]);

  useEffect(() => {
    if (pendingQuery) {
      sendMessage(pendingQuery, mode);
      clearPending();
    }
  }, [pendingQuery, clearPending, sendMessage, mode]);

  const handleSubmit = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    sendMessage(text, mode);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full">
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-slate-700/50 px-4 bg-[#0b1120]/60">
        {MODE_TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setMode(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer border-b-2 ${
              mode === key
                ? "border-indigo-500 text-indigo-300"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-600 gap-3">
            <Network size={48} className="text-slate-700" />
            <p className="text-sm">Select a demo query or type a question below</p>
          </div>
        )}
        {messages.map((msg) => (
          <ChatBubble key={msg.id} msg={msg} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={messagesEnd} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-700/50 bg-[#0b1120]/60">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about drug interactions..."
            disabled={loading}
            rows={1}
            className="flex-1 bg-slate-800/60 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50 resize-none disabled:opacity-50"
          />
          <button
            onClick={handleSubmit}
            disabled={loading || !input.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl p-2.5 transition-colors cursor-pointer"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
