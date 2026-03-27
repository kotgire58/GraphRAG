import { create } from "zustand";
import type { Message, Mode, GraphStats, HealthStatus, GraphData } from "./types";

interface AppState {
  mode: Mode;
  setMode: (mode: Mode) => void;

  messages: Message[];
  addMessage: (msg: Message) => void;
  clearMessages: () => void;

  sessionId: string | null;
  setSessionId: (id: string) => void;

  loading: boolean;
  setLoading: (v: boolean) => void;

  health: HealthStatus | null;
  setHealth: (h: HealthStatus) => void;

  stats: GraphStats | null;
  setStats: (s: GraphStats) => void;

  graphData: GraphData;
  setGraphData: (d: GraphData) => void;
  mergeGraphData: (d: GraphData) => void;

  lastResponse: Message | null;
}

export const useStore = create<AppState>((set, get) => ({
  mode: "graph",
  setMode: (mode) => set({ mode }),

  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  clearMessages: () => set({ messages: [], sessionId: null, lastResponse: null }),

  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),

  loading: false,
  setLoading: (v) => set({ loading: v }),

  health: null,
  setHealth: (h) => set({ health: h }),

  stats: null,
  setStats: (s) => set({ stats: s }),

  graphData: { nodes: [], links: [] },
  setGraphData: (d) => set({ graphData: d }),
  mergeGraphData: (incoming) => {
    const current = get().graphData;
    const nodeIds = new Set(current.nodes.map((n) => n.id));
    const linkKeys = new Set(
      current.links.map((l) => `${l.source}-${l.type}-${l.target}`)
    );
    const newNodes = incoming.nodes.filter((n) => !nodeIds.has(n.id));
    const newLinks = incoming.links.filter(
      (l) => !linkKeys.has(`${l.source}-${l.type}-${l.target}`)
    );
    set({
      graphData: {
        nodes: [...current.nodes, ...newNodes],
        links: [...current.links, ...newLinks],
      },
    });
  },

  lastResponse: null,
}));
