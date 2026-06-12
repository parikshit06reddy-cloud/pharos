import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { AgentChat } from "./AgentChat";

interface NavItem { to: string; label: string; roles: string[] }

const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", roles: ["front_desk", "doctor", "admin"] },
  { to: "/intake", label: "New case", roles: ["front_desk", "admin"] },
  { to: "/cases", label: "All cases", roles: ["front_desk", "admin"] },
  { to: "/worklist", label: "My worklist", roles: ["doctor"] },
  { to: "/quick-brief", label: "Quick brief", roles: ["front_desk", "doctor", "admin"] },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [agentOpen, setAgentOpen] = useState(false);
  if (!user) return null;
  const items = NAV.filter((n) => n.roles.includes(user.role));

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `block px-3 py-2 rounded-lg text-sm transition ${
      isActive ? "bg-beam/10 text-beam border border-beam/30" : "text-muted hover:text-mist hover:bg-surface/60"
    }`;

  return (
    <div className="min-h-full flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-line bg-surface/40 flex flex-col">
        <div className="flex items-center gap-2 px-4 h-16 border-b border-line">
          <div className="w-8 h-8 rounded-lg border border-beam/40 grid place-items-center">
            <div className="w-2 h-2 rounded-full bg-beam shadow-[0_0_12px_3px_rgba(13,148,136,0.45)]" />
          </div>
          <div>
            <div className="font-display font-bold text-mist leading-none">Pharos</div>
            <div className="text-[10px] text-muted">case management</div>
          </div>
        </div>
        <nav className="p-3 space-y-1 flex-1">
          {items.map((n) => <NavLink key={n.to} to={n.to} className={linkCls}>{n.label}</NavLink>)}
        </nav>
        <div className="p-3 border-t border-line text-xs">
          <div className="text-mist font-medium">{user.name}</div>
          <div className="text-muted capitalize">{user.role.replace(/_/g, " ")}{user.specialty ? ` · ${user.specialty}` : ""}</div>
          <button onClick={() => { logout(); navigate("/login"); }}
            className="mt-2 text-muted hover:text-sev-serious transition">Sign out</button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-16 border-b border-line flex items-center justify-between px-6">
          <div className="text-[12px] text-muted">Synthetic data only · Pharos informs; the clinician decides · Not for clinical use</div>
          <button onClick={() => setAgentOpen((v) => !v)}
            className="text-xs px-3 py-1.5 rounded-lg border border-beam/40 text-beam hover:bg-beam/10 transition">
            {agentOpen ? "Close assistant" : "Ask assistant"}
          </button>
        </header>
        <div className="flex-1 min-h-0 flex">
          <main className="flex-1 min-w-0 overflow-y-auto p-6"><Outlet /></main>
          {agentOpen && (
            <div className="w-96 shrink-0 border-l border-line bg-surface/40">
              <AgentChat onNavigate={(to) => navigate(to)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
