import { ChevronRight } from "lucide-react";

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

const KNOWN_LABELS: Record<string, string> = {
  "PT-": "Patient",
  Metformin: "Drug",
  Warfarin: "Drug",
  Fluconazole: "Drug",
  Amiodarone: "Drug",
  Digoxin: "Drug",
  Glipizide: "Drug",
  Atorvastatin: "Drug",
  Simvastatin: "Drug",
  Lisinopril: "Drug",
  CYP: "Enzyme",
  "P-glycoprotein": "Transporter",
  OCT2: "Transporter",
  MATE: "Transporter",
  "QT Prolongation": "Condition",
  Torsades: "Condition",
  Diabetes: "Condition",
  Hypertension: "Condition",
  Bleeding: "Condition",
  "Dr.": "Physician",
  Metro: "Hospital",
};

function guessLabel(name: string): string {
  for (const [prefix, label] of Object.entries(KNOWN_LABELS)) {
    if (name.startsWith(prefix) || name.includes(prefix)) return label;
  }
  return "Drug";
}

interface PathSegment {
  node: string;
  rel?: string;
}

function parsePath(raw: string): PathSegment[] {
  const parts = raw.split(/\s*-\[/).flatMap((chunk, i) => {
    if (i === 0) return [{ node: chunk.trim() }];
    const [relPart, rest] = chunk.split(/\]->\s*/);
    const segments: PathSegment[] = [];
    if (relPart && rest) {
      segments.push({ node: "", rel: relPart.replace(/\{.*\}/, "").trim() });
      segments.push({ node: rest.trim() });
    }
    return segments;
  });
  return parts.filter((p) => p.node || p.rel);
}

interface TraversalPathProps {
  path: string;
  compact?: boolean;
}

export default function TraversalPath({ path, compact }: TraversalPathProps) {
  const segments = parsePath(path);

  return (
    <div className={`flex items-center flex-wrap gap-1 ${compact ? "text-xs" : "text-sm"}`}>
      {segments.map((seg, i) => {
        if (seg.rel) {
          return (
            <span
              key={i}
              className="flex items-center gap-0.5 text-slate-400 font-mono text-[10px] uppercase tracking-wide"
            >
              <ChevronRight size={12} className="text-slate-500" />
              {seg.rel}
              <ChevronRight size={12} className="text-slate-500" />
            </span>
          );
        }
        if (!seg.node) return null;
        const label = guessLabel(seg.node);
        const color = LABEL_COLORS[label] ?? "#6366f1";
        return (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded px-2 py-0.5 font-medium border"
            style={{
              backgroundColor: `${color}18`,
              borderColor: `${color}40`,
              color,
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full inline-block"
              style={{ backgroundColor: color }}
            />
            {seg.node}
          </span>
        );
      })}
    </div>
  );
}
