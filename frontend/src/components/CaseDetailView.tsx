import { useCallback, useEffect, useState } from "react";
import { assignCase, getCase, listSpecialists, pickupCase, resolveCase, routeCase } from "../api";
import { useAuth } from "../auth";
import type { CaseDetail, Specialist } from "../types";
import { PriorityBadge, StatusBadge, timeAgo } from "../lib/ui";
import { DecisionBrief } from "./DecisionBrief";

function RoutingPanel({ detail, onChange }: { detail: CaseDetail; onChange: () => void }) {
  const { user } = useAuth();
  const [specialists, setSpecialists] = useState<Specialist[]>([]);
  const [busy, setBusy] = useState(false);
  const canAssign = user?.role === "front_desk" || user?.role === "admin";

  useEffect(() => { if (canAssign) listSpecialists().then(setSpecialists).catch(() => {}); }, [canAssign]);

  async function assign(doctorId: number) {
    setBusy(true);
    try { await assignCase(detail.id, doctorId); onChange(); } finally { setBusy(false); }
  }
  async function reroute() {
    setBusy(true);
    try { await routeCase(detail.id); onChange(); } finally { setBusy(false); }
  }

  return (
    <div className="bg-surface/50 border border-line rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm text-mist tracking-wide">Suggested experts</h3>
        {canAssign && <button onClick={reroute} disabled={busy} className="text-[11px] text-muted hover:text-beam transition">Re-route</button>}
      </div>
      <div className="space-y-2">
        {detail.route_suggestions.slice(0, 3).map((m, i) => {
          const doc = specialists.find((s) => s.specialty === m.specialty);
          return (
            <div key={m.specialist_id} className="border border-line rounded-lg p-3">
              <div className="flex items-center gap-2">
                {i === 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-beam/15 text-beam border border-beam/30">best match</span>}
                <span className="text-sm text-mist font-medium">{m.specialty}</span>
                <span className="ml-auto font-mono text-[11px] text-grounded">{Math.round(m.score * 100)}%</span>
              </div>
              <div className="text-[11px] text-muted mt-1">{m.name} · load {m.current_load}/{m.capacity}{m.available ? "" : " · unavailable"}</div>
              {m.rationale && <div className="text-[11px] text-muted mt-1">{m.rationale}</div>}
              {canAssign && (
                <button onClick={() => assign(doc?.id ?? m.specialist_id)} disabled={busy || !!detail.assigned_doctor}
                  className="mt-2 text-[11px] px-2.5 py-1 rounded-lg border border-beam/40 text-beam hover:bg-beam/10 disabled:opacity-40 transition">
                  {detail.assigned_doctor ? "Assigned" : `Assign to ${m.name}`}
                </button>
              )}
            </div>
          );
        })}
      </div>
      {detail.assigned_doctor && (
        <div className="text-xs text-mist">Assigned to <span className="text-beam">{detail.assigned_doctor.name}</span> ({detail.assigned_doctor.specialty})</div>
      )}
    </div>
  );
}

function DoctorActions({ detail, onChange }: { detail: CaseDetail; onChange: () => void }) {
  const { user } = useAuth();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (user?.role !== "doctor" || detail.assigned_doctor_id !== user.id) return null;

  async function act(fn: () => Promise<any>) {
    setBusy(true);
    try { await fn(); onChange(); } finally { setBusy(false); }
  }

  return (
    <div className="bg-surface/50 border border-line rounded-xl p-4 space-y-2">
      <h3 className="font-display text-sm text-mist tracking-wide">Doctor actions</h3>
      {detail.status === "assigned" && (
        <button onClick={() => act(() => pickupCase(detail.id))} disabled={busy}
          className="w-full bg-beam text-ink font-semibold rounded-lg py-2 text-sm hover:brightness-110 transition">Pick up case</button>
      )}
      {detail.status === "in_review" && (
        <>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Clinician note (optional)"
            className="w-full bg-ink/60 border border-line rounded-lg px-3 py-2 text-sm h-16 resize-none focus:outline-none focus:border-beam/60" />
          <div className="flex gap-2">
            <button onClick={() => act(() => resolveCase(detail.id, "complete", note))} disabled={busy}
              className="flex-1 bg-grounded/20 border border-grounded/40 text-grounded rounded-lg py-2 text-sm hover:bg-grounded/30 transition">Complete</button>
            <button onClick={() => act(() => resolveCase(detail.id, "return", note))} disabled={busy}
              className="flex-1 border border-line text-muted rounded-lg py-2 text-sm hover:text-mist transition">Return</button>
            <button onClick={() => act(() => resolveCase(detail.id, "escalate", note))} disabled={busy}
              className="flex-1 border border-sev-critical/40 text-sev-critical rounded-lg py-2 text-sm hover:bg-sev-critical/10 transition">Escalate</button>
          </div>
        </>
      )}
      {["completed", "returned", "escalated"].includes(detail.status) && (
        <p className="text-xs text-muted">Case {detail.status}.</p>
      )}
    </div>
  );
}

function Timeline({ detail }: { detail: CaseDetail }) {
  return (
    <div className="bg-surface/50 border border-line rounded-xl p-4">
      <h3 className="font-display text-sm text-mist tracking-wide mb-2">Activity</h3>
      <ol className="space-y-2">
        {detail.timeline.map((e, i) => (
          <li key={i} className="flex gap-2 text-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-beam mt-1.5 shrink-0" />
            <div>
              <span className="text-mist">{e.type.replace(/_/g, " ")}</span>
              {e.actor && <span className="text-muted"> · {e.actor}</span>}
              <span className="text-muted"> · {timeAgo(e.created_at)}</span>
              {e.detail?.note && <div className="text-muted mt-0.5">“{e.detail.note}”</div>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function CaseDetailView({ caseId }: { caseId: number }) {
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getCase(caseId).then(setDetail).catch((e) => setError(String(e.message || e)));
  }, [caseId]);
  useEffect(() => { setDetail(null); setError(null); load(); }, [caseId, load]);

  if (error) return <div className="text-sm text-sev-serious">Could not load case: {error}</div>;
  if (!detail) return <div className="text-sm text-muted">Loading case…</div>;

  const p = detail.patient || {};
  const demo = p.demographics || {};
  return (
    <div className="grid xl:grid-cols-[minmax(0,1fr)_340px] gap-5">
      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs text-muted">{detail.case_ref}</span>
            <StatusBadge status={detail.status} />
            <PriorityBadge priority={detail.priority} />
            {detail.injection_detected && <span className="text-[10px] px-2 py-0.5 rounded-full border border-sev-serious/40 text-sev-serious">injection ignored</span>}
          </div>
          <h2 className="font-display text-lg text-mist mt-1">{detail.candidate_drug}</h2>
          <p className="text-sm text-muted">{detail.question}</p>
        </div>
        <div className="bg-surface/50 border border-line rounded-xl p-4 text-xs text-mist grid grid-cols-2 gap-y-1 gap-x-4">
          <div><span className="text-muted">Age:</span> {demo.age_years ?? "—"}</div>
          <div><span className="text-muted">Sex:</span> {demo.sex ?? "—"}</div>
          <div><span className="text-muted">Pregnancy:</span> {demo.pregnancy_status ?? "n/a"}</div>
          <div><span className="text-muted">eGFR:</span> {(p.labs || []).find((l: any) => l.name?.toLowerCase() === "egfr")?.value ?? "—"}</div>
          <div className="col-span-2"><span className="text-muted">Conditions:</span> {(p.conditions || []).map((c: any) => c.name).join(", ") || "none"}</div>
          <div className="col-span-2"><span className="text-muted">Current meds:</span> {(p.current_medications || []).map((m: any) => m.name).join(", ") || "none"}</div>
          <div className="col-span-2"><span className="text-muted">Allergies:</span> {(p.allergies || []).map((a: any) => a.substance).join(", ") || "none"}</div>
        </div>
        {detail.brief && <DecisionBrief brief={detail.brief} showGovernance={false} />}
      </div>
      <div className="space-y-4">
        <RoutingPanel detail={detail} onChange={load} />
        <DoctorActions detail={detail} onChange={load} />
        <Timeline detail={detail} />
      </div>
    </div>
  );
}
