import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createCase } from "../api";
import { CaseForm } from "../components/CaseForm";
import { CaseDetailView } from "../components/CaseDetailView";
import type { CaseInput } from "../types";

export function Intake() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);

  async function run(input: CaseInput) {
    setBusy(true); setError(null);
    try {
      const detail = await createCase(input);
      setCreatedId(detail.id);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {!createdId && (
        <section className="bg-surface/60 border border-line rounded-xl p-4 shadow-panel max-w-xl">
          <h1 className="font-display text-sm text-mist tracking-wide mb-3">New case — synthetic patient context</h1>
          <CaseForm onRun={run} busy={busy} cta="File case & triage" />
          {error && <p className="text-xs text-sev-serious mt-2">{error}</p>}
        </section>
      )}
      {busy && <div className="border border-line rounded-xl p-6 text-muted text-sm">Triaging and routing…</div>}
      {createdId && (
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <h1 className="font-display text-lg text-mist">Case filed</h1>
            <button onClick={() => setCreatedId(null)} className="text-[12px] text-muted hover:text-beam transition">+ File another case</button>
            <button onClick={() => navigate(`/cases/${createdId}`)} className="text-[12px] text-beam hover:underline">Open full case →</button>
          </div>
          <CaseDetailView caseId={createdId} />
        </div>
      )}
    </div>
  );
}
