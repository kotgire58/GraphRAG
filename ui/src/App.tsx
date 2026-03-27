import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ToolsPanel from "./components/ToolsPanel";
import ChatPage from "./pages/ChatPage";

export default function App() {
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);

  const handleDemoQuery = useCallback((q: string) => {
    setPendingQuery(q);
  }, []);

  const clearPending = useCallback(() => {
    setPendingQuery(null);
  }, []);

  return (
    <div className="h-screen w-screen flex bg-[#0f172a] text-white overflow-hidden">
      <Sidebar onSubmitQuery={handleDemoQuery} />
      <ChatPage pendingQuery={pendingQuery} clearPending={clearPending} />
      <ToolsPanel />
    </div>
  );
}
