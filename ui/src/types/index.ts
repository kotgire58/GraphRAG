export interface SeedFactItem {
  fact: string;
  score: number;
  from_name: string;
  rel_type: string;
  to_name: string;
}

export interface TraversalExplanation {
  query: string;
  entities_identified: string[];
  seed_facts_via_vector_search: {
    fact: string;
    similarity_score: number;
    why_relevant: string;
  }[];
  mandatory_facts_always_included: string[];
  critical_path: string;
  total_facts_in_context: number;
  how_it_works: string;
}

export interface ChatResponse {
  answer: string;
  mode: string;
  session_id: string;
  sources: SourceItem[];
  traversal_path: string[] | null;
  tools_used: string[];
  traversal_explanation?: TraversalExplanation | null;
  seed_facts?: SeedFactItem[] | null;
  traversal_graph?: GraphData | null;
}

export interface SourceItem {
  content?: string;
  filename?: string;
  similarity?: number;
  fact?: string;
}

export interface GraphStats {
  total_nodes: number;
  total_relationships: number;
  nodes_by_label: Record<string, number>;
}

export interface GraphNode {
  id: string;
  name: string;
  label: string;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface HealthStatus {
  postgres: string;
  neo4j: string;
  llm: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode: string;
  sources?: SourceItem[];
  traversal_path?: string[] | null;
  tools_used?: string[];
  traversal_explanation?: TraversalExplanation | null;
  seed_facts?: SeedFactItem[] | null;
  traversal_graph?: GraphData | null;
}

export type Mode = "vector" | "graph" | "agentic";
