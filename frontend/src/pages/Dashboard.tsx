import { useEffect, useState } from "react";
import { getMetrics } from "../api";
import type { Metrics } from "../types";

function Kpi({ label, value, tone = "mist" }: { label: string; value: number; tone?: string }) {
  const color = { mist: "text-mist", beam: "text-beam", caution: "text-sev-caution", critical: "text-sev-critical", grounded: "text-grounded" }[tone] || "text-mist";
  return (
    <div className="bg-surface/60 border border-line rounded-xl p-4">
      <div className={`font-display text-3xl font-bold tabular ${color}`}>{value}</div>
      <div className="text-xs text-muted mt-1">{label}</div>
    </div>
  );
}

export function Dashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  useEffect(() => { getMetrics().then(setM).catch(() => {}); }, []);
  if (!m) return <div className="text-sm text-muted">Loading dashboard…</div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="font-display text-xl text-mist">Operations dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Kpi label="Open cases" value={m.open} tone="beam" />
        <Kpi label="Unassigned" value={m.unassigned} tone="caution" />
        <Kpi label="Overdue (SLA)" value={m.overdue} tone="critical" />
        <Kpi label="Completed" value={m.by_status.completed || 0} tone="grounded" />
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div className="bg-surface/50 border border-line rounded-xl p-4">
          <h3 className="font-display text-sm text-mist mb-3">Cases by status</h3>
          <div className="space-y-2">
            {Object.entries(m.by_status).map(([k, v]) => (
              <div key={k} className="flex items-center gap-3 text-sm">
                <span className="text-muted w-32 capitalize">{k.replace(/_/g, " ")}</span>
                <div className="flex-1 h-2 bg-line rounded-full overflow-hidden border border-line">
                  <div className="h-full bg-beam/60" style={{ width: `${Math.min(100, v * 12)}%` }} />
                </div>
                <span className="font-mono text-xs text-mist w-6 text-right tabular">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-surface/50 border border-line rounded-xl p-4">
          <h3 className="font-display text-sm text-mist mb-3">Specialist load</h3>
          <div className="space-y-2">
            {m.by_specialty.map((s) => (
              <div key={s.name} className="flex items-center gap-3 text-sm">
                <span className="text-muted w-36 truncate" title={s.name}>{s.specialty}</span>
                <div className="flex-1 h-2 bg-line rounded-full overflow-hidden border border-line">
                  <div className={`h-full ${s.load / s.capacity > 0.8 ? "bg-sev-caution" : "bg-grounded/60"}`}
                    style={{ width: `${Math.min(100, (s.load / Math.max(s.capacity, 1)) * 100)}%` }} />
                </div>
                <span className="font-mono text-xs text-mist w-10 text-right tabular">{s.load}/{s.capacity}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
