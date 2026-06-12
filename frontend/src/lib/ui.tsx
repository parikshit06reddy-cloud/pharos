import type { Severity, TriageTier } from "../types";

export const SEV: Record<Severity, { label: string; chip: string; dot: string; order: number }> = {
  critical: { label: "Critical", chip: "bg-sev-critical/15 text-sev-critical border-sev-critical/40", dot: "bg-sev-critical", order: 3 },
  serious: { label: "Serious", chip: "bg-sev-serious/15 text-sev-serious border-sev-serious/40", dot: "bg-sev-serious", order: 2 },
  caution: { label: "Caution", chip: "bg-sev-caution/15 text-sev-caution border-sev-caution/40", dot: "bg-sev-caution", order: 1 },
  info: { label: "Info", chip: "bg-sev-info/15 text-sev-info border-sev-info/40", dot: "bg-sev-info", order: 0 },
};

export const TIER: Record<TriageTier, { label: string; cls: string }> = {
  urgent: { label: "Urgent — escalate now", cls: "bg-sev-critical/15 border-sev-critical/50 text-sev-critical" },
  review_recommended: { label: "Review recommended", cls: "bg-sev-caution/15 border-sev-caution/50 text-sev-caution" },
  informational: { label: "Informational", cls: "bg-sev-info/12 border-sev-info/40 text-sev-info" },
};

export const STAGES: Record<string, string> = {
  intake: "De-identify & validate", retrieval: "Retrieve evidence (Foundry IQ)",
  injection_scan: "Screen retrieved text for injection", specialist: "Safety specialist",
  synthesis: "Synthesize brief", verifier: "Grounding gate & abstention",
  triage: "Triage & escalate", brief: "Decision brief ready",
};

const STATUS_CLS: Record<string, string> = {
  new: "border-line text-muted", triaged: "border-beam/40 text-beam", routed: "border-beam/40 text-beam",
  assigned: "border-sev-caution/50 text-sev-caution", in_review: "border-beam/50 text-beam",
  completed: "border-grounded/50 text-grounded", returned: "border-line text-muted",
  escalated: "border-sev-critical/50 text-sev-critical",
};
const PRIORITY_CLS: Record<string, string> = {
  routine: "border-line text-muted", urgent: "border-sev-caution/50 text-sev-caution",
  emergent: "border-sev-critical/50 text-sev-critical",
};

export function Pill({ children, tone = "beam" }: { children: any; tone?: string }) {
  const map: Record<string, string> = {
    beam: "border-beam/40 text-beam", muted: "border-line text-muted", grounded: "border-grounded/40 text-grounded",
  };
  return <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full border ${map[tone]}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${STATUS_CLS[status] || "border-line text-muted"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${PRIORITY_CLS[priority] || "border-line text-muted"}`}>
      {priority}
    </span>
  );
}

export function csv(s: string) {
  return s.split(",").map((x) => x.trim()).filter(Boolean);
}

export function timeAgo(iso: string): string {
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).getTime();
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}
