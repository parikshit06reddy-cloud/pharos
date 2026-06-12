import { useEffect, useState } from "react";
import { getJSON } from "../api";
import { Pill } from "../lib/ui";

type Health = {
  providers: { retrieval: string; router: string; agent: string };
  foundry_iq_ready: boolean;
  offline_capable: boolean;
};

const PROVIDER_LABEL: Record<string, string> = {
  local: "Offline (BM25)",
  foundry_iq: "Microsoft Foundry IQ",
  foundry: "Microsoft Foundry IQ",
  foundry_replay: "Foundry IQ (replay fixture)",
  replay: "Foundry IQ (replay fixture)",
};

export function ProviderBanner() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    getJSON<Health>("/health").then(setHealth).catch(() => {});
  }, []);
  if (!health) return null;

  const retr = health.providers.retrieval;
  const label = PROVIDER_LABEL[retr] ?? retr;
  const live = retr === "foundry_iq" || retr === "foundry";
  const replay = retr === "foundry_replay" || retr === "replay";

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Pill tone={live ? "grounded" : replay ? "beam" : "muted"}>
        Retrieval: {label}
      </Pill>
      {health.offline_capable && !live && (
        <span className="text-[10px] text-muted">Credential-free demo · flip RETRIEVAL_PROVIDER=foundry_iq for live Foundry IQ</span>
      )}
    </div>
  );
}
