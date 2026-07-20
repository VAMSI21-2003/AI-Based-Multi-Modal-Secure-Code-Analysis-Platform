import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Bot, User, Send, Sparkles, ShieldQuestion } from "lucide-react";
import PageShell from "../components/PageShell";
import { askCopilot, type CopilotResponse } from "../api/copilot";

interface Message { role: "user" | "assistant"; text: string; sources?: string[]; }

export default function Copilot() {
  const [params] = useSearchParams();
  const scanId = params.get("scan") ?? undefined;
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Hi! I'm the Security Copilot. Ask me about a dangerous API, a CWE, or a vulnerability class — no external AI service required, everything below is answered deterministically from the platform's own knowledge base." },
  ]);
  const [input, setInput] = useState("");
  const [suggested, setSuggested] = useState<string[]>([
    "Why is strcpy dangerous?", "What is CWE-416?", "What does buffer overflow mean?", "Why is this code flagged as vulnerable?",
  ]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (question: string) => {
    if (!question.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const r: CopilotResponse = await askCopilot(question, scanId);
      setMessages((m) => [...m, { role: "assistant", text: r.answer, sources: r.sources }]);
      setSuggested(r.suggested);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", text: "Something went wrong reaching the copilot backend." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageShell title="AI Security Copilot" subtitle="Deterministic Q&A — no external LLM required">
      <div className="card flex flex-col h-[70vh] max-h-[720px]">
        <div className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-4">
          {messages.map((m, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${m.role === "assistant" ? "bg-(--accent)/20 text-(--accent)" : "bg-(--surface-3) text-(--text-secondary)"}`}>
                {m.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
              </div>
              <div className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${m.role === "assistant" ? "bg-(--surface-3) text-(--text-secondary)" : "bg-(--accent)/15 text-(--text-primary)"}`}>
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {m.sources.map((s) => <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-(--surface-2) text-(--text-muted) mono">{s}</span>)}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-(--accent)/20 text-(--accent)"><Bot size={16} /></div>
              <div className="rounded-xl px-4 py-3 bg-(--surface-3) text-(--text-muted) text-sm flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-(--text-muted) animate-pulse-soft" />
                <span className="w-1.5 h-1.5 rounded-full bg-(--text-muted) animate-pulse-soft" style={{ animationDelay: "0.2s" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-(--text-muted) animate-pulse-soft" style={{ animationDelay: "0.4s" }} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {suggested.length > 0 && (
          <div className="px-5 pb-3 flex flex-wrap gap-2">
            {suggested.map((s) => (
              <button key={s} onClick={() => send(s)} className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-(--surface-3) hover:bg-(--surface-2) text-(--text-secondary) transition-colors">
                <Sparkles size={11} className="text-(--accent)" /> {s}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); send(input); }}
          className="flex items-center gap-2 p-4 border-t border-(--border-hairline)"
        >
          <ShieldQuestion size={18} className="text-(--text-muted) shrink-0" />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={scanId ? "Ask about strcpy, CWE-120, or 'explain this function'..." : "Ask about a dangerous API or CWE..."}
            className="flex-1 bg-(--surface-3) border border-(--border-hairline) rounded-lg px-3 py-2.5 text-sm focus-ring outline-none"
          />
          <button type="submit" disabled={loading || !input.trim()} className="p-2.5 rounded-lg bg-(--accent) text-white disabled:opacity-40 hover:brightness-110 transition">
            <Send size={16} />
          </button>
        </form>
      </div>
    </PageShell>
  );
}
