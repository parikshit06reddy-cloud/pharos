import { useRef, useState } from "react";
import { confirmAgentAction, streamAgent } from "../api";
import type { AgentMessage, ProposedAction } from "../types";

const SUGGESTIONS = ["Show unassigned cases", "Who is the expert for case 1?", "My worklist"];

export function AgentChat({ onNavigate }: { onNavigate: (to: string) => void }) {
  const [messages, setMessages] = useState<AgentMessage[]>([{
    role: "assistant",
    text: "Hi — I'm the Pharos assistant. I can find cases, suggest the right specialist, and prepare assignments for your confirmation. Try a suggestion below.",
  }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement | null>(null);

  function scroll() {
    requestAnimationFrame(() => scroller.current?.scrollTo({ top: 1e9, behavior: "smooth" }));
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    const history = messages.map((m) => ({ role: m.role, text: m.text }));
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    scroll();
    abort.current?.abort();
    abort.current = new AbortController();
    try {
      await streamAgent(q, history, (e) => {
        if (e.event === "message") {
          setMessages((m) => [...m, {
            role: "assistant", text: e.data.text,
            data: e.data.navigate ? { navigate: e.data.navigate } : undefined,
            proposed_action: e.data.proposed_action ?? null,
          }]);
          scroll();
        }
      }, abort.current.signal);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, I couldn't reach the assistant service." }]);
    } finally {
      setBusy(false);
      scroll();
    }
  }

  async function confirm(action: ProposedAction, idx: number) {
    setBusy(true);
    try {
      const out: any = await confirmAgentAction(action);
      const ref = out?.result?.case_ref ?? "the case";
      setMessages((m) => {
        const copy = [...m];
        copy[idx] = { ...copy[idx], proposed_action: null };
        copy.push({ role: "assistant", text: `Done — ${action.summary} (${ref}).`, data: out?.result?.id ? { navigate: `/cases/${out.result.id}` } : undefined });
        return copy;
      });
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", text: `Could not complete: ${e?.message || e}` }]);
    } finally {
      setBusy(false);
      scroll();
    }
  }

  function cancel(idx: number) {
    setMessages((m) => {
      const copy = [...m];
      copy[idx] = { ...copy[idx], proposed_action: null };
      copy.push({ role: "assistant", text: "Okay, cancelled. Nothing was changed." });
      return copy;
    });
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 h-12 flex items-center border-b border-line">
        <h3 className="font-display text-sm text-mist">Assistant</h3>
        <span className="ml-2 text-[10px] text-muted">tools · human-confirmed actions</span>
      </div>

      <div ref={scroller} className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div className={`inline-block text-sm rounded-xl px-3 py-2 max-w-[92%] whitespace-pre-wrap text-left ${
              m.role === "user" ? "bg-beam/15 text-mist border border-beam/30" : "bg-surface/70 text-mist border border-line"
            }`}>
              {m.text}
            </div>
            {m.data?.navigate && (
              <div className="mt-1">
                <button onClick={() => onNavigate(m.data.navigate)} className="text-[11px] text-beam hover:underline">Open →</button>
              </div>
            )}
            {m.proposed_action && (
              <div className="mt-2 border border-sev-caution/40 bg-sev-caution/5 rounded-xl p-3 text-left">
                <div className="text-[11px] uppercase tracking-wider text-sev-caution mb-1">Confirm action</div>
                <div className="text-sm text-mist">{m.proposed_action.summary}</div>
                {m.proposed_action.evidence && <div className="text-[11px] text-muted mt-1">{m.proposed_action.evidence}</div>}
                <div className="flex gap-2 mt-2">
                  <button onClick={() => confirm(m.proposed_action!, i)} disabled={busy}
                    className="text-[11px] px-3 py-1 rounded-lg bg-beam text-ink font-semibold hover:brightness-110 disabled:opacity-50 transition">Confirm</button>
                  <button onClick={() => cancel(i)} disabled={busy}
                    className="text-[11px] px-3 py-1 rounded-lg border border-line text-muted hover:text-mist transition">Cancel</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {busy && <div className="text-xs text-muted">Thinking…</div>}
      </div>

      <div className="p-3 border-t border-line space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} disabled={busy}
              className="text-[10px] px-2 py-1 rounded-full border border-line text-muted hover:border-beam/50 hover:text-mist transition">{s}</button>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Ask the assistant…"
            className="flex-1 bg-ink/60 border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-beam/60" />
          <button onClick={() => send(input)} disabled={busy}
            className="px-3 py-2 rounded-lg bg-beam text-ink font-semibold text-sm hover:brightness-110 disabled:opacity-50 transition">Send</button>
        </div>
      </div>
    </div>
  );
}
