import type {
  AgentMessage, AuthUser, CaseDetail, CaseInput, CaseSummary, Metrics,
  Specialist, StreamEvent,
} from "./types";

const TOKEN_KEY = "pharos_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: authHeaders({ "content-type": "application/json", ...(init.headers as any) }),
  });
  if (res.status === 401) {
    setToken(null);
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = JSON.stringify((await res.json()).detail ?? detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

// --- auth -------------------------------------------------------------------
export async function login(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  const out = await req<{ token: string; user: AuthUser }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(out.token);
  return out;
}
export const me = () => req<AuthUser>("/api/auth/me");
export const listSpecialists = () => req<Specialist[]>("/api/auth/specialists");

// --- cases ------------------------------------------------------------------
export const createCase = (input: CaseInput) =>
  req<CaseDetail>("/api/cases", { method: "POST", body: JSON.stringify(input) });

export function listCases(opts: { status?: string; mine?: boolean; unassigned?: boolean } = {}): Promise<CaseSummary[]> {
  const p = new URLSearchParams();
  if (opts.status) p.set("status", opts.status);
  if (opts.mine) p.set("mine", "true");
  if (opts.unassigned) p.set("unassigned", "true");
  const qs = p.toString();
  return req<CaseSummary[]>(`/api/cases${qs ? `?${qs}` : ""}`);
}
export const getCase = (id: number) => req<CaseDetail>(`/api/cases/${id}`);
export const routeCase = (id: number) => req<CaseDetail>(`/api/cases/${id}/route`, { method: "POST" });
export const assignCase = (id: number, doctorId: number) =>
  req<CaseDetail>(`/api/cases/${id}/assign`, { method: "POST", body: JSON.stringify({ doctor_id: doctorId }) });
export const pickupCase = (id: number) => req<CaseDetail>(`/api/cases/${id}/pickup`, { method: "POST" });
export const resolveCase = (id: number, outcome: string, note?: string) =>
  req<CaseDetail>(`/api/cases/${id}/resolve`, { method: "POST", body: JSON.stringify({ outcome, note }) });

// --- dashboard --------------------------------------------------------------
export const getMetrics = () => req<Metrics>("/api/dashboard/metrics");

// --- agent (SSE) ------------------------------------------------------------
export async function streamAgent(
  message: string,
  history: AgentMessage[],
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  await streamSSE("/api/agent/chat", { message, history }, onEvent, signal);
}

export async function confirmAgentAction(action: any): Promise<any> {
  return req("/api/agent/confirm", { method: "POST", body: JSON.stringify({ action }) });
}

// --- decision brief live stream (quick brief demo) --------------------------
export async function streamBrief(
  input: CaseInput,
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  await streamSSE("/brief", input, onEvent, signal);
}

async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`request failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) onEvent({ event, data: JSON.parse(data) });
    }
  }
}

export async function getJSON<T>(path: string): Promise<T> {
  return req<T>(path);
}
export async function deleteSession(id: string): Promise<void> {
  await fetch(`/session/${encodeURIComponent(id)}`, { method: "DELETE", headers: authHeaders() });
}
