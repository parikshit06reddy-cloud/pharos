export type Severity = "critical" | "serious" | "caution" | "info";
export type TriageTier = "urgent" | "review_recommended" | "informational";

export interface Subject {
  kind?: string | null;
  interacting_with?: string | null;
  detail?: string | null;
}

export interface Finding {
  finding_id: string;
  type: string;
  severity: Severity;
  subject: Subject;
  statement: string;
  citation_keys: string[];
  grounding: string;
  rationale?: string | null;
  specialist: string;
}

export interface Option {
  option: string;
  citation_keys: string[];
}

export interface Confidence {
  level: string;
  grounded_share: number;
  gaps: string[];
}

export interface Passage {
  citation_key: string;
  source_id: string;
  source_type: string;
  title: string;
  section: string;
  drug_name?: string | null;
  text: string;
  source_version?: string | null;
  url?: string | null;
  provider: string;
}

export interface Brief {
  case_id: string;
  model_version: string;
  latency_ms: number;
  triage_tier: TriageTier;
  abstained: boolean;
  answer: string;
  findings: Finding[];
  options: Option[];
  confidence: Confidence;
  handoff_summary: string;
  citations: Passage[];
  emergency_resources: string[];
  limitations: string[];
  safety_flags: { injection_detected?: boolean };
}

export interface CaseInput {
  case_id: string;
  session_id: string;
  demographics: { age_years?: number; sex?: string; pregnancy_status?: string };
  conditions: { name: string }[];
  current_medications: { name: string }[];
  allergies: { substance: string }[];
  labs: { name: string; value: number; unit?: string }[];
  candidate_drug: { name: string };
  question: string;
  consent: { synthetic: boolean; no_phi: boolean };
}

export type StreamEvent = { event: string; data: any };

// --- enterprise workflow ----------------------------------------------------
export type Role = "front_desk" | "doctor" | "admin";
export type CaseStatusValue =
  | "new" | "triaged" | "routed" | "assigned" | "in_review"
  | "completed" | "returned" | "escalated";
export type PriorityValue = "routine" | "urgent" | "emergent";

export interface AuthUser {
  id: number;
  username: string;
  name: string;
  role: Role;
  specialty?: string | null;
}

export interface Specialist extends AuthUser {
  expertise_keywords?: string[];
  capacity?: number;
  available?: boolean;
}

export interface SpecialistMatch {
  specialist_id: number;
  name: string;
  specialty: string;
  score: number;
  matched_terms: string[];
  rationale: string;
  capacity: number;
  current_load: number;
  available: boolean;
}

export interface CaseSummary {
  id: number;
  case_ref: string;
  title: string;
  status: CaseStatusValue;
  priority: PriorityValue;
  candidate_drug: string;
  triage_tier: string | null;
  abstained: boolean;
  injection_detected: boolean;
  route_specialty: string | null;
  assigned_doctor_id: number | null;
  created_at: string;
  updated_at: string;
  target_window_minutes: number | null;
}

export interface TimelineEvent {
  type: string;
  actor: string | null;
  detail: Record<string, any>;
  created_at: string;
}

export interface CaseDetail extends CaseSummary {
  question: string;
  patient: any;
  brief: Brief | null;
  route_suggestions: SpecialistMatch[];
  assigned_doctor: { id: number; name: string; specialty: string } | null;
  timeline: TimelineEvent[];
}

export interface Metrics {
  by_status: Record<string, number>;
  open: number;
  unassigned: number;
  overdue: number;
  by_specialty: { specialty: string; name: string; load: number; capacity: number; available: boolean }[];
}

// --- agent chatbot ----------------------------------------------------------
export interface ProposedAction {
  tool: string;
  args: Record<string, any>;
  summary: string;
  evidence?: string;
}

export interface AgentMessage {
  role: "user" | "assistant";
  text: string;
  tool?: string | null;
  data?: any;
  proposed_action?: ProposedAction | null;
}
