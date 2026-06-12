import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

const DEMO = [
  { username: "frontdesk", label: "Front desk" },
  { username: "hart", label: "Dr. Hart (Hematology)" },
  { username: "admin", label: "Admin" },
];

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("frontdesk");
  const [password, setPassword] = useState("pharos123");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(u = username, p = password) {
    setBusy(true); setError(null);
    try {
      await login(u, p);
      navigate("/dashboard");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setBusy(false);
    }
  }

  const field = "w-full bg-ink/60 border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-beam/60";

  return (
    <div className="min-h-full grid place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg border border-beam/40 grid place-items-center">
            <div className="w-2.5 h-2.5 rounded-full bg-beam shadow-[0_0_14px_4px_rgba(13,148,136,0.45)]" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold text-mist leading-none">Pharos</h1>
            <p className="text-[12px] text-muted mt-0.5">Hospital medication case management</p>
          </div>
        </div>

        <div className="bg-surface/60 border border-line rounded-xl p-5 shadow-panel space-y-3">
          <div><label className="text-[11px] uppercase tracking-wider text-muted mb-1 block">Username</label>
            <input className={field} value={username} onChange={(e) => setUsername(e.target.value)} /></div>
          <div><label className="text-[11px] uppercase tracking-wider text-muted mb-1 block">Password</label>
            <input className={field} type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()} /></div>
          {error && <p className="text-xs text-sev-serious">{error}</p>}
          <button disabled={busy} onClick={() => submit()}
            className="w-full bg-beam text-ink font-semibold rounded-lg py-2.5 text-sm hover:brightness-110 disabled:opacity-50 transition">
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <div className="pt-2 border-t border-line">
            <p className="text-[11px] text-muted mb-1.5">Demo accounts (password <span className="font-mono">pharos123</span>):</p>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map((d) => (
                <button key={d.username} onClick={() => { setUsername(d.username); setPassword("pharos123"); submit(d.username, "pharos123"); }}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-line text-muted hover:border-beam/50 hover:text-mist transition">
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="text-[11px] text-muted mt-4 text-center">Synthetic data only. Not for clinical use.</p>
      </div>
    </div>
  );
}
