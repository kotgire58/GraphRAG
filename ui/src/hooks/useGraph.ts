import { useCallback, useEffect } from "react";
import axios from "axios";
import type { GraphData, GraphStats } from "../types";
import { apiUrl } from "../api";
import { useStore } from "../store";

export function useGraph() {
  const { stats, setStats, mergeGraphData, graphData } = useStore();

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await axios.get<GraphStats>(apiUrl("/graph/stats"));
      setStats(data);
    } catch {
      /* health check will show offline */
    }
  }, [setStats]);

  const fetchNode = useCallback(
    async (name: string) => {
      try {
        const { data } = await axios.get(
          apiUrl(`/graph/node/${encodeURIComponent(name)}`)
        );
        const centerLabel: string =
          data.node?.label ?? Object.keys(data.node ?? {})[0] ?? "Drug";
        const nodes: GraphData["nodes"] = [
          { id: name, name, label: centerLabel },
        ];
        const links: GraphData["links"] = [];

        for (const rel of data.relationships ?? []) {
          if (!rel.neighbor) continue;
          nodes.push({
            id: rel.neighbor,
            name: rel.neighbor,
            label: rel.neighbor_label ?? "Drug",
          });
          if (rel.direction === "outgoing") {
            links.push({ source: name, target: rel.neighbor, type: rel.type });
          } else {
            links.push({ source: rel.neighbor, target: name, type: rel.type });
          }
        }

        mergeGraphData({ nodes, links });
      } catch {
        /* silent */
      }
    },
    [mergeGraphData]
  );

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return { stats, graphData, fetchNode, fetchStats };
}
