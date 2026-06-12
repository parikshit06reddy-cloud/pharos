import { useRef, useState } from "react";
import { deleteSession, streamBrief } from "../api";
import { CaseForm } from "../components/CaseForm";
import { DecisionBrief, ReasoningStream } from "../components/DecisionBrief";
import { ReasoningRoster } from "../components/ReasoningRoster";
import type { Brief, CaseInput, StreamEvent } from "../types";

export function QuickBrief() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [busy, setBusy] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  async function run(c: CaseInput) {
    abort.current?.abort();
    abort.current = new AbortController();
    setBusy(true); setError(null); setBrief(null); setEvents([]); setLatency(null);
    try {
      await streamBrief(c, (e) => {
        if (e.event === "brief") { setBrief(e.data as Brief); setLatency((e.data as Brief).latency_ms); }
        else setEvents((prev) => [...prev, e]);
      }, abort.current.signal);
    } catch (err: any) {
      if (err?.name !== "AbortError") setError("Could not reach the Pharos API.");
    } finally { setBusy(false); }
  }

  async function onDelete() {
    if (!brief) return;
    await deleteSession(brief.case_id);
    setBrief(null); setEvents([]); setLatency(null);
  }

  return (
    <div className="max-w-6xl">
      <div className="mb-4">
        <h1 className="font-display text-xl text-mist">Quick brief</h1>
        <p className="text-sm text-muted">Run the live grounded reasoning pipeline without filing a case.</p>
      </div>
      <div className="grid lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] gap-5">
        <div className="space-y-5">
          <section className="bg-surface/60 border border-line rounded-xl p-4 shadow-panel">
            <h2 className="font-display text-sm text-mist tracking-wide mb-3">Synthetic patient context</h2>
            <CaseForm onRun={run} busy={busy} />
          </section>
          <ReasoningStream events={events} busy={busy} latency={latency} />
          <ReasoningRoster />
        </div>
        <div>
          {error && <div className="bg-sev-serious/10 border border-sev-serious/40 rounded-xl p-4 text-sm text-sev-serious">{error}</div>}
          {!error && !brief && !busy && (
            <div className="h-full min-h-[300px] grid place-items-center border border-dashed border-line rounded-xl text-center px-6">
              <div>
                <p className="text-mist font-display">The decision brief appears here.</p>
                <p className="text-muted text-sm mt-1">Pick a sample case or enter your own, then generate a brief.</p>
              </div>
            </div>
          )}
          {!error && !brief && busy && <div className="border border-line rounded-xl p-6 text-muted text-sm">Reasoning over the evidence…</div>}
          {brief && <DecisionBrief brief={brief} onDelete={onDelete} />}
        </div>
      </div>
    </div>
  );
}
