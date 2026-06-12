import { useState } from "react";
import { SAMPLE_CASES } from "../sampleCases";
import type { CaseInput } from "../types";
import { csv } from "../lib/ui";

const field =
  "w-full bg-ink/60 border border-line rounded-lg px-3 py-2 text-sm placeholder:text-muted/60 focus:outline-none focus:border-beam/60";
const lab = "text-[11px] uppercase tracking-wider text-muted mb-1 block";

export function CaseForm({ onRun, busy, cta = "Generate decision brief" }: {
  onRun: (c: CaseInput) => void; busy: boolean; cta?: string;
}) {
  const [drug, setDrug] = useState("fluconazole");
  const [question, setQuestion] = useState("My patient on warfarin needs an antifungal. Any interaction with fluconazole?");
  const [age, setAge] = useState("64");
  const [sex, setSex] = useState("female");
  const [preg, setPreg] = useState("not_applicable");
  const [conds, setConds] = useState("atrial fibrillation");
  const [meds, setMeds] = useState("warfarin");
  const [allergies, setAllergies] = useState("");
  const [egfr, setEgfr] = useState("");

  function build(): CaseInput {
    const labs = egfr ? [{ name: "eGFR", value: Number(egfr), unit: "mL/min/1.73m2" }] : [];
    return {
      case_id: `ui_${Date.now()}`, session_id: `ui_${Date.now()}`,
      demographics: { age_years: age ? Number(age) : undefined, sex, pregnancy_status: preg },
      conditions: csv(conds).map((name) => ({ name })),
      current_medications: csv(meds).map((name) => ({ name })),
      allergies: csv(allergies).map((substance) => ({ substance })),
      labs, candidate_drug: { name: drug }, question, consent: { synthetic: true, no_phi: true },
    };
  }

  function loadSample(i: number) {
    const c = SAMPLE_CASES[i].case;
    setDrug(c.candidate_drug.name); setQuestion(c.question);
    setAge(String(c.demographics.age_years ?? "")); setSex(c.demographics.sex ?? "unknown");
    setPreg(c.demographics.pregnancy_status ?? "not_applicable");
    setConds(c.conditions.map((x) => x.name).join(", "));
    setMeds(c.current_medications.map((x) => x.name).join(", "));
    setAllergies(c.allergies.map((x) => x.substance).join(", "));
    setEgfr(String(c.labs.find((l) => l.name.toLowerCase() === "egfr")?.value ?? ""));
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {SAMPLE_CASES.map((s, i) => (
          <button key={i} onClick={() => loadSample(i)} title={s.note}
            className="text-[11px] px-2.5 py-1 rounded-full border border-line text-muted hover:border-beam/50 hover:text-mist transition">
            {s.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2"><label className={lab}>Candidate drug</label><input className={field} value={drug} onChange={(e) => setDrug(e.target.value)} /></div>
        <div><label className={lab}>Age</label><input className={field} value={age} onChange={(e) => setAge(e.target.value)} inputMode="numeric" /></div>
        <div><label className={lab}>Sex</label>
          <select className={field} value={sex} onChange={(e) => setSex(e.target.value)}>
            <option value="female">female</option><option value="male">male</option><option value="other">other</option><option value="unknown">unknown</option>
          </select></div>
        <div><label className={lab}>Pregnancy</label>
          <select className={field} value={preg} onChange={(e) => setPreg(e.target.value)}>
            <option value="not_applicable">n/a</option><option value="pregnant">pregnant</option><option value="not_pregnant">not pregnant</option><option value="unknown">unknown</option>
          </select></div>
        <div><label className={lab}>eGFR (optional)</label><input className={field} value={egfr} onChange={(e) => setEgfr(e.target.value)} inputMode="numeric" placeholder="—" /></div>
        <div className="col-span-2"><label className={lab}>Current medications</label><input className={field} value={meds} onChange={(e) => setMeds(e.target.value)} placeholder="comma-separated" /></div>
        <div><label className={lab}>Conditions</label><input className={field} value={conds} onChange={(e) => setConds(e.target.value)} placeholder="comma-separated" /></div>
        <div><label className={lab}>Allergies</label><input className={field} value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="comma-separated" /></div>
        <div className="col-span-2"><label className={lab}>Clinical question</label><textarea className={`${field} h-20 resize-none`} value={question} onChange={(e) => setQuestion(e.target.value)} /></div>
      </div>
      <button disabled={busy} onClick={() => onRun(build())}
        className="w-full bg-beam text-ink font-semibold rounded-lg py-2.5 text-sm hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition">
        {busy ? "Working…" : cta}
      </button>
      <p className="text-[11px] text-muted leading-relaxed">Synthetic, no-PHI cases only. Pharos informs; the clinician decides. Not for clinical use.</p>
    </div>
  );
}
