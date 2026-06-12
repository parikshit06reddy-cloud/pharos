import { useEffect, useState } from "react";
import { getJSON } from "../api";

type Agent = { id: string; role: string; pattern: string; description: string };

export function ReasoningRoster() {
  const [agents, setAgents] = useState<Agent[]>([]);
  useEffect(() => {
    getJSON<{ reasoning_agents: Agent[] }>("/health")
      .then((h) => setAgents(h.reasoning_agents))
      .catch(() => {});
  }, []);
  if (!agents.length) return null;

  return (
    <section className="bg-surface/40 border border-line rounded-xl p-4">
      <h3 className="font-display text-sm text-mist tracking-wide mb-2">Reasoning agent roster</h3>
      <p className="text-[10px] text-muted mb-2">Named roles · critic/verifier gate · parallel specialists</p>
      <ul className="space-y-2">
        {agents.map((a) => (
          <li key={a.id} className="text-xs">
            <div className="flex items-center gap-2">
              <span className="text-beam font-medium">{a.role}</span>
              <span className="font-mono text-[10px] text-muted px-1.5 py-0.5 rounded border border-line">{a.pattern}</span>
            </div>
            <p className="text-muted mt-0.5 leading-snug">{a.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
