import { useMemo, useState } from "react";
import { getJSON } from "../api";
import type { Brief, Finding, Passage, StreamEvent } from "../types";
import { Pill, ROLE_LABEL, SEV, STAGES, TIER } from "../lib/ui";

function stageDetail(e: StreamEvent): string {
  if (e.event === "retrieval") {
    const prov = e.data.provider_class ?? e.data.provider;
    return `${e.data.count} passages · ${prov}`;
  }
  if (e.event === "injection_scan") return e.data.injection_detected ? "injection attempt found & ignored" : "clean";
  if (e.event === "specialist") return `${e.data.findings.length} finding(s)`;
  if (e.event === "verifier") {
    const dropped = e.data.dropped_unsupported ?? 0;
    return (
      `grounded ${Math.round((e.data.grounded_share ?? 0) * 100)}%`
      + (dropped > 0 ? ` · dropped ${dropped} unsupported` : "")
      + (e.data.conflict ? " · sources conflict" : "")
      + (e.data.abstained ? " · abstain" : "")
    );
  }
  if (e.event === "triage") return e.data.tier;
  if (e.event === "intake") return `${e.data.redactions?.length ?? 0} redaction(s)`;
  if (e.event === "synthesis") return e.data.answerable ? "answerable" : `withheld: ${e.data.reason ?? "—"}`;
  return "";
}

function expandableBody(e: StreamEvent): string | null {
  if (e.event === "specialist" && e.data.findings?.length) {
    return e.data.findings.map((f: Finding) => `• [${f.severity}] ${f.statement}`).join("\n");
  }
  if (e.event === "retrieval" && e.data.sources?.length) {
    return e.data.sources.slice(0, 6).map((s: { citation_key: string; section: string }) => `• ${s.citation_key} (${s.section})`).join("\n");
  }
  if (e.event === "verifier" && e.data.grounding?.length) {
    return e.data.grounding.map((g: { finding_id: string; grounding: string }) => `• ${g.finding_id}: ${g.grounding}`).join("\n");
  }
  return null;
}

export function ReasoningStream({ events, busy, latency }: { events: StreamEvent[]; busy: boolean; latency: number | null }) {
  const [open, setOpen] = useState<number | null>(null);
  const stages = useMemo(() => events.filter((e) => e.event !== "brief"), [events]);

  return (
    <div className="relative bg-surface/60 border border-line rounded-xl p-4 overflow-hidden">
      {busy && <div className="beam-line" />}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-display text-sm tracking-wide text-mist">Live reasoning trace</h3>
          <p className="text-[10px] text-muted mt-0.5">Named agents · critic/verifier gate · streamed stage-by-stage</p>
        </div>
        {latency != null && <span className="font-mono text-[11px] text-beam tabular">{latency} ms end-to-end</span>}
      </div>
      <ol className="space-y-1.5">
        {stages.length === 0 && <li className="text-sm text-muted">Awaiting a case…</li>}
        {stages.map((e, i) => {
          const role = (e.data.role as string) || ROLE_LABEL[e.event] || e.event;
          const stage = e.event === "specialist" ? STAGES.specialist : STAGES[e.event] ?? e.event;
          const detail = stageDetail(e);
          const body = expandableBody(e);
          const isOpen = open === i;
          return (
            <li key={i} className="text-sm">
              <button
                type="button"
                disabled={!body}
                onClick={() => setOpen(isOpen ? null : i)}
                className={`w-full text-left flex items-start gap-2 ${body ? "hover:bg-surface/40 rounded-lg px-1 -mx-1 py-0.5" : ""}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${e.event === "injection_scan" && e.data.injection_detected ? "bg-sev-serious" : e.event === "verifier" ? "bg-grounded" : "bg-beam"}`} />
                <span className="min-w-0 flex-1">
                  <span className="text-[10px] uppercase tracking-wider text-beam/80 block">{role}</span>
                  <span className="text-mist">{stage}</span>
                  {detail && <span className="font-mono text-[11px] text-muted"> — {detail}</span>}
                </span>
                {body && <span className="text-[10px] text-muted shrink-0">{isOpen ? "▾" : "▸"}</span>}
              </button>
              {isOpen && body && (
                <pre className="ml-3.5 mt-1 text-[10px] text-muted whitespace-pre-wrap font-mono leading-relaxed border-l border-line pl-2">{body}</pre>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function FlagCard({ f, onCite }: { f: Finding; onCite: (k: string) => void }) {
  const s = SEV[f.severity];
  return (
    <div className="bg-panel/70 border border-line rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${s.chip}`}>{s.label}</span>
        <span className="text-[11px] uppercase tracking-wider text-muted">{f.type.replace(/_/g, " ")}</span>
        <span className="ml-auto text-[10px] font-mono text-muted">{f.grounding}</span>
      </div>
      <p className="text-sm text-mist leading-relaxed">{f.statement}</p>
      {f.rationale && <p className="text-[12px] text-muted mt-1.5">{f.rationale}</p>}
      <div className="flex flex-wrap gap-1.5 mt-2">
        {f.citation_keys.map((k) => (
          <button key={k} onClick={() => onCite(k)}
            className="font-mono text-[10px] px-2 py-0.5 rounded border border-beam/30 text-beam hover:bg-beam/10 transition">{k}</button>
        ))}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div><span className="text-muted">{k}: </span><span className="text-mist">{v}</span></div>;
}

function GovernanceTabs({ sessionId }: { sessionId?: string }) {
  const [tab, setTab] = useState<"passport" | "audit" | "card" | null>(null);
  const [data, setData] = useState<any>(null);
  async function open(t: "passport" | "audit" | "card") {
    setTab(t); setData(null);
    const path = t === "passport" ? `/data-passport${sessionId ? `?session_id=${sessionId}` : ""}` : t === "audit" ? "/audit-log" : "/model-card";
    setData(await getJSON<any>(path));
  }
  const tabs: [string, "passport" | "audit" | "card"][] = [["Data passport", "passport"], ["Audit log", "audit"], ["Model card", "card"]];
  return (
    <div className="bg-surface/50 border border-line rounded-xl p-4">
      <div className="flex gap-2 mb-3">
        {tabs.map(([label, key]) => (
          <button key={key} onClick={() => open(key)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition ${tab === key ? "border-beam/60 text-beam bg-beam/10" : "border-line text-muted hover:text-mist"}`}>{label}</button>
        ))}
      </div>
      {!tab && <p className="text-xs text-muted">Governance: what's collected, the tamper-evident audit chain, and the system's intended use & limits.</p>}
      {tab && !data && <p className="text-xs text-muted">Loading…</p>}
      {tab === "passport" && data && (
        <div className="text-xs text-mist space-y-1.5">
          <Row k="Retention" v={data.retention} /><Row k="Secondary use" v={data.secondary_use} />
          <Row k="Telemetry" v={data.telemetry} /><Row k="Redactions this session" v={String((data.redactions_this_session || []).length)} />
        </div>
      )}
      {tab === "audit" && data && (
        <div className="text-xs space-y-2">
          <div className="flex items-center gap-2"><Pill tone={data.chain_valid ? "grounded" : "muted"}>{data.chain_valid ? "chain valid" : "chain broken"}</Pill><span className="text-muted">{data.entries.length} entries (no PHI — hashes only)</span></div>
          {data.entries.slice(-4).reverse().map((e: any, i: number) => (
            <div key={i} className="font-mono text-[10px] text-muted border border-line rounded p-2 break-all">
              {e.candidate_drug} · {e.triage_tier} · fp {String(e.case_fingerprint).slice(0, 12)}…
            </div>
          ))}
        </div>
      )}
      {tab === "card" && data && (
        <div className="text-xs text-mist space-y-1.5">
          <Row k="Intended use" v={data.intended_use} /><Row k="Out of scope" v={(data.out_of_scope || []).join("; ")} />
          <Row k="Regulatory framing" v={data.regulatory_framing} />
        </div>
      )}
    </div>
  );
}

function CitationDrawer({ passage, onClose }: { passage: Passage | null; onClose: () => void }) {
  if (!passage) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div className="relative w-full max-w-md h-full bg-surface border-l border-line p-5 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <span className="font-mono text-[11px] text-beam break-all">{passage.citation_key}</span>
          <button onClick={onClose} className="text-muted hover:text-mist text-sm">✕</button>
        </div>
        <h3 className="font-display text-mist text-sm mb-1">{passage.title}</h3>
        <div className="text-[11px] text-muted mb-3">{passage.section.replace(/_/g, " ")} · {passage.provider}{passage.source_version ? ` · ${passage.source_version}` : ""}</div>
        <p className="text-sm text-mist leading-relaxed whitespace-pre-wrap">{passage.text}</p>
        {passage.url && <a href={passage.url} target="_blank" rel="noreferrer" className="inline-block mt-4 text-xs text-beam underline break-all">Source</a>}
        <p className="text-[10px] text-muted mt-4">Curated public-label excerpt for a synthetic demo. Not for clinical use.</p>
      </div>
    </div>
  );
}

export function DecisionBrief({ brief, onDelete, showGovernance = true }: {
  brief: Brief; onDelete?: () => void; showGovernance?: boolean;
}) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const tier = TIER[brief.triage_tier];
  const conf = brief.confidence;
  const findings = [...brief.findings].sort((a, b) => SEV[b.severity].order - SEV[a.severity].order);
  const citations = useMemo(() => {
    const m = new Map<string, Passage>();
    brief.citations.forEach((c) => m.set(c.citation_key, c));
    return m;
  }, [brief]);

  return (
    <div className="space-y-4">
      <div className={`border rounded-xl px-4 py-3 flex items-center gap-3 ${tier.cls}`}>
        <span className="font-display font-semibold text-sm">{tier.label}</span>
        {brief.safety_flags?.injection_detected && <Pill tone="muted">injection attempt ignored</Pill>}
        <span className="ml-auto font-mono text-[11px] tabular opacity-80">{brief.latency_ms} ms</span>
      </div>

      {brief.emergency_resources.length > 0 && (
        <div className="bg-sev-critical/10 border border-sev-critical/40 rounded-xl p-3 text-sm">
          {brief.emergency_resources.map((r, i) => <div key={i} className="text-sev-critical">{r}</div>)}
        </div>
      )}

      <div className={`rounded-xl p-4 border ${brief.abstained ? "bg-sev-caution/8 border-sev-caution/40" : "bg-panel/70 border-line"}`}>
        {brief.abstained && <div className="text-[11px] uppercase tracking-wider text-sev-caution mb-1">Abstained — insufficient grounded evidence</div>}
        <p className="text-[15px] text-mist leading-relaxed">{brief.answer}</p>
      </div>

      {findings.length > 0 && (
        <div className="space-y-2.5">
          <h3 className="font-display text-sm text-muted tracking-wide">Safety flags · {findings.length}</h3>
          {findings.map((f) => <FlagCard key={f.finding_id} f={f} onCite={setOpenKey} />)}
        </div>
      )}

      {brief.options.length > 0 && (
        <div className="bg-surface/50 border border-line rounded-xl p-4">
          <h3 className="font-display text-sm text-muted tracking-wide mb-2">Options to weigh — you decide</h3>
          <ul className="space-y-1.5">
            {brief.options.map((o, i) => <li key={i} className="text-sm text-mist flex gap-2"><span className="text-beam">→</span>{o.option}</li>)}
          </ul>
        </div>
      )}

      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted">Confidence</span>
        <span className="font-display font-semibold capitalize text-mist">{conf.level}</span>
        <div className="flex-1 h-1.5 bg-line rounded-full overflow-hidden border border-line">
          <div className="h-full bg-grounded" style={{ width: `${Math.round(conf.grounded_share * 100)}%` }} />
        </div>
        <span className="font-mono text-[11px] text-grounded tabular">{Math.round(conf.grounded_share * 100)}% grounded</span>
      </div>
      {conf.gaps.length > 0 && (
        <ul className="text-[12px] text-muted space-y-1">{conf.gaps.map((g, i) => <li key={i}>• {g}</li>)}</ul>
      )}

      <details className="bg-surface/40 border border-line rounded-xl p-3">
        <summary className="text-xs text-muted cursor-pointer">Clinician hand-off summary (copyable)</summary>
        <pre className="mt-2 text-[11px] text-mist whitespace-pre-wrap font-mono leading-relaxed">{brief.handoff_summary}</pre>
      </details>

      {showGovernance && <GovernanceTabs sessionId={brief.case_id} />}

      {onDelete && (
        <button onClick={onDelete} className="text-[11px] text-muted hover:text-sev-serious transition">Delete this session & purge its audit rows</button>
      )}

      <CitationDrawer passage={openKey ? citations.get(openKey) ?? null : null} onClose={() => setOpenKey(null)} />
    </div>
  );
}
