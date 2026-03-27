import { useCallback } from "react";
import axios from "axios";
import type { ChatResponse, Message, Mode } from "../types";
import { apiUrl } from "../api";
import { useStore } from "../store";

export function useChat() {
  const {
    addMessage,
    setLoading,
    setSessionId,
    sessionId,
    loading,
    messages,
  } = useStore();

  const sendMessage = useCallback(
    async (text: string, mode: Mode) => {
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        mode,
      };
      addMessage(userMsg);
      setLoading(true);

      try {
        const { data } = await axios.post<ChatResponse>(apiUrl("/chat"), {
          message: text,
          mode,
          session_id: sessionId,
        });

        if (data.session_id) {
          setSessionId(data.session_id);
        }

        const assistantMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          mode: data.mode,
          sources: data.sources,
          traversal_path: data.traversal_path,
          tools_used: data.tools_used,
          traversal_explanation: data.traversal_explanation,
          seed_facts: data.seed_facts,
          traversal_graph: data.traversal_graph,
        };
        addMessage(assistantMsg);

        if (data.traversal_graph?.nodes?.length) {
          useStore.getState().setGraphData(data.traversal_graph);
        }

        useStore.setState({ lastResponse: assistantMsg });
      } catch (err) {
        const errMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Request failed"}`,
          mode,
        };
        addMessage(errMsg);
      } finally {
        setLoading(false);
      }
    },
    [addMessage, setLoading, setSessionId, sessionId]
  );

  return { sendMessage, messages, loading };
}
