"""Pipeline orchestrator — wires every stage together and streams progress events.

run_pipeline() is a generator: it yields {"event", "data"} dicts for the live reasoning
panel (SSE) and finishes by yielding the final Decision Brief. The same function is used
by the eval harness (which just consumes the final brief).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from . import injection_guard, synthesizer, verifier
from . import triage as triage_mod
from .governance import audit_log
from .intake import run_intake
from .retrieval import get_provider
from .retrieval.base import tokenize
from .schemas import DecisionBrief, EvidencePassage, SafetyFinding
from .specialists import ALL as SPECIALISTS
from .specialists.base import SpecialistContext

_CANDIDATE_SECTIONS = (
    "boxed_warning",
    "contraindications",
    "drug_interactions",
    "warnings",
    "use_in_specific_populations",
    "dosage_and_administration",
    "geriatric_use",
    "pediatric_use",
    "pregnancy",
)
_MED_SECTIONS = ("drug_interactions", "contraindications", "warnings")


def _event(name: str, data: dict) -> dict:
    return {"event": name, "data": data}


def _retrieve_pool(provider, case) -> list[EvidencePassage]:
    query = case.question or case.candidate_drug.name
    pool: list[EvidencePassage] = []
    pool += provider.retrieve(
        query,
        drug_rxcuis=[case.candidate_drug.rxcui or ""],
        drug_names=[case.candidate_drug.name],
        sections=_CANDIDATE_SECTIONS,
        k=20,
    )
    for med in case.current_medications:
        pool += provider.retrieve(
            query,
            drug_rxcuis=[med.rxcui or ""],
            drug_names=[med.name],
            sections=_MED_SECTIONS,
            k=8,
        )
    # de-dupe by citation_key
    seen, out = set(), []
    for p in pool:
        if p.citation_key not in seen:
            seen.add(p.citation_key)
            out.append(p)
    return out


def run_pipeline(raw_case: dict, session_id: str | None = None) -> Iterator[dict]:
    t0 = time.perf_counter()
    provider = get_provider()

    # 1) Intake + de-identify
    intake = run_intake(raw_case)
    case = intake.case
    yield _event(
        "intake",
        {
            "candidate": case.candidate_drug.name,
            "conditions": [c.name for c in case.conditions],
            "current_medications": [m.name for m in case.current_medications],
            "allergies": [a.substance for a in case.allergies],
            "labs": [f"{l.name}={l.value}{l.unit or ''}" for l in case.labs],
            "redactions": intake.redactions,
            "rxcui_resolved": intake.rxcui_resolved,
        },
    )

    # 2) Retrieval (Foundry IQ adapter)
    pool = _retrieve_pool(provider, case)
    yield _event(
        "retrieval",
        {
            "provider": pool[0].provider if pool else "local_corpus",
            "count": len(pool),
            "sources": [{"citation_key": p.citation_key, "title": p.title, "section": p.section} for p in pool],
        },
    )

    # 3) Injection guard (retrieved text is DATA, not instructions)
    pool, detections = injection_guard.scan_passages(pool)
    question_injection = injection_guard.scan_text(case.question)
    injection_detected = bool(detections or question_injection)
    yield _event(
        "injection_scan",
        {
            "injection_detected": injection_detected,
            "detections": [{"citation_key": d.citation_key, "snippet": d.snippet} for d in detections],
            "question_flagged": bool(question_injection),
        },
    )

    # 4) Parallel safety specialists (each reasons ONLY from retrieved passages)
    class_index = getattr(provider, "drug_classes", {})
    ctx = SpecialistContext(case=case, passages=pool, class_index=class_index)
    findings: list[SafetyFinding] = []
    with ThreadPoolExecutor(max_workers=len(SPECIALISTS)) as ex:
        futures = {ex.submit(m.analyze, ctx): m.NAME for m in SPECIALISTS}
        for fut in futures:
            name = futures[fut]
            result = fut.result()
            findings += result
            yield _event("specialist", {"specialist": name, "findings": [f.model_dump() for f in result]})

    # 5) Synthesize
    draft = synthesizer.synthesize(case, findings, pool)
    yield _event(
        "synthesis",
        {
            "answerable": draft["answerable"],
            "reason": draft["answer_reason"],
            "n_findings": len(draft["findings"]),
            "n_options": len(draft["options"]),
        },
    )

    # 6) Verify (grounding gate + abstention)
    drug_terms = set(tokenize(case.candidate_drug.name)) | {
        t for m in case.current_medications for t in tokenize(m.name)
    }
    vr = verifier.verify(draft, pool, drug_terms)
    yield _event(
        "verifier",
        {
            "abstained": vr["abstained"],
            "grounded_share": vr["confidence"].grounded_share,
            "conflict": vr["conflict"],
            # Surface the critic's filtering: how many candidate findings were dropped as UNSUPPORTED.
            "findings_considered": len(draft["findings"]),
            "findings_kept": len(vr["findings"]),
            "dropped_unsupported": len(draft["findings"]) - len(vr["findings"]),
            "grounding": [{"finding_id": f.finding_id, "grounding": f.grounding.value} for f in vr["findings"]],
        },
    )

    # 7) Triage
    tr = triage_mod.triage(case, vr["findings"], vr["abstained"])
    yield _event("triage", {"tier": tr["tier"].value, "resources": tr["resources"]})

    # 8) Assemble final Decision Brief
    kept = vr["findings"]
    referenced = {k for f in kept for k in f.citation_keys} | {k for o in vr["options"] for k in o.citation_keys}
    by_key = {p.citation_key: p for p in pool}
    citations = [by_key[k] for k in referenced if k in by_key]
    answer = (tr["emergency_message"] + vr["answer"]).strip()

    brief = DecisionBrief(
        case_id=case.case_id,
        latency_ms=int((time.perf_counter() - t0) * 1000),
        triage_tier=tr["tier"],
        abstained=vr["abstained"],
        answer=answer,
        findings=kept,
        options=vr["options"],
        confidence=vr["confidence"],
        citations=citations,
        emergency_resources=tr["resources"],
        safety_flags={"injection_detected": injection_detected},
    )
    brief.handoff_summary = triage_mod.build_handoff(brief, case)

    # 9) Audit (tamper-evident, no PHI)
    audit_log.append(
        case_id=case.case_id,
        candidate=case.candidate_drug.name,
        model_version=brief.model_version,
        citation_keys=list(referenced),
        triage_tier=brief.triage_tier.value,
        abstained=brief.abstained,
        injection_detected=injection_detected,
        case_fp=audit_log.case_fingerprint(raw_case),
    )

    yield _event("brief", brief.model_dump())


def run_to_brief(raw_case: dict) -> DecisionBrief:
    """Convenience for evals/tests: run the generator and return the final brief."""
    final = None
    for ev in run_pipeline(raw_case):
        if ev["event"] == "brief":
            final = ev["data"]
    return DecisionBrief.model_validate(final)
