import { useEffect, useState } from "react";
import { listCases } from "../api";
import { CaseDetailView } from "../components/CaseDetailView";
import type { CaseSummary } from "../types";
import { PriorityBadge, StatusBadge, timeAgo } from "../lib/ui";

type Filter = "all" | "unassigned" | "mine" | "open";

export function Worklist({ mine = false, title }: { mine?: boolean; title: string }) {
  const [filter, setFilter] = useState<Filter>(mine ? "mine" : "unassigned");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  function load() {
    setLoading(true);
    const opts: any = {};
    if (filter === "unassigned") opts.unassigned = true;
    if (filter === "mine") opts.mine = true;
    listCases(opts)
      .then((cs) => {
        const filtered = filter === "open"
          ? cs.filter((c) => !["completed", "returned"].includes(c.status))
          : cs;
        setCases(filtered);
        if (filtered.length && selected == null) setSelected(filtered[0].id);
      })
      .finally(() => setLoading(false));
  }
  useEffect(load, [filter, mine]); // eslint-disable-line react-hooks/exhaustive-deps

  const filters: Filter[] = mine ? ["mine", "all"] : ["unassigned", "open", "all"];

  return (
    <div className="grid lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)] gap-5 h-full">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-lg text-mist">{title}</h1>
          <button onClick={load} className="text-[11px] text-muted hover:text-beam transition">Refresh</button>
        </div>
        <div className="flex gap-1.5">
          {filters.map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-[11px] px-2.5 py-1 rounded-full border capitalize transition ${
                filter === f ? "border-beam/50 text-beam bg-beam/10" : "border-line text-muted hover:text-mist"}`}>
              {f}
            </button>
          ))}
        </div>
        <div className="space-y-2 overflow-y-auto">
          {loading && <p className="text-sm text-muted">Loading…</p>}
          {!loading && cases.length === 0 && <p className="text-sm text-muted">No cases in this queue.</p>}
          {cases.map((c) => (
            <button key={c.id} onClick={() => setSelected(c.id)}
              className={`w-full text-left border rounded-xl p-3 transition ${
                selected === c.id ? "border-beam/50 bg-beam/5" : "border-line hover:border-beam/30"}`}>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-muted">{c.case_ref}</span>
                <PriorityBadge priority={c.priority} />
                <span className="ml-auto"><StatusBadge status={c.status} /></span>
              </div>
              <div className="text-sm text-mist mt-1">{c.candidate_drug}</div>
              <div className="text-[11px] text-muted truncate">{c.route_specialty ? `→ ${c.route_specialty}` : ""} · {timeAgo(c.updated_at)}</div>
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-y-auto">
        {selected ? <CaseDetailView caseId={selected} /> : (
          <div className="h-full min-h-[300px] grid place-items-center border border-dashed border-line rounded-xl text-center px-6">
            <p className="text-muted text-sm">Select a case to review it.</p>
          </div>
        )}
      </div>
    </div>
  );
}
