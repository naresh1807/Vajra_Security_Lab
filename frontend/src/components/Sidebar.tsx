import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

interface NavItem {
  label: string;
  to?: string;
  phase?: string;
}

const NAV: NavItem[] = [
  { label: "Dashboard", to: "/" },
  { label: "Projects", to: "/projects" },
  { label: "Recon", to: "/projects", phase: "inside a project" },
  { label: "Attack Surface", to: "/projects", phase: "inside a project" },
  { label: "HTTP Inspector", to: "/projects", phase: "inside a project" },
  { label: "API Mapper", to: "/projects", phase: "inside a project" },
  { label: "Parameters", to: "/projects", phase: "inside a project" },
  { label: "JS Inspector", to: "/projects", phase: "inside a project" },
  { label: "Auth Flow", to: "/projects", phase: "inside a project" },
  { label: "Analyzer", to: "/projects", phase: "inside a project" },
  { label: "Vajra Diff", to: "/projects", phase: "inside a project" },
  { label: "Investigations", to: "/projects", phase: "inside a project" },
  { label: "Findings", to: "/projects", phase: "inside a project" },
  { label: "Evidence", to: "/projects", phase: "inside an investigation" },
  { label: "Reports", to: "/projects", phase: "inside an investigation" },
  { label: "Verify Evidence Bundle", to: "/evidence/verify" },
  { label: "Hunt Copilot", to: "/projects", phase: "inside a project" },
  { label: "Practice Labs", to: "/practice" },
  { label: "Account Security", to: "/account/security" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  return (
    <aside className="flex h-full w-60 flex-col border-r border-vajra-border bg-vajra-panel">
      <div className="flex items-center gap-2 border-b border-vajra-border px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-vajra-accent to-vajra-accent2 text-sm font-bold text-white">
          V
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-100">Vajra Security Lab</div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Bug Bounty Workstation</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV.map((item) =>
          item.to ? (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive ? "bg-vajra-accent/15 text-violet-200" : "text-slate-300 hover:bg-white/5"
                }`
              }
            >
              <span>{item.label}</span>
              {item.phase && <span className="text-[10px] text-slate-500">{item.phase}</span>}
            </NavLink>
          ) : (
            <div
              key={item.label}
              className="flex cursor-not-allowed items-center justify-between rounded-md px-3 py-2 text-sm text-slate-600"
              title={`Not built yet - ${item.phase}`}
            >
              <span>{item.label}</span>
              <span className="text-[10px] text-slate-600">{item.phase}</span>
            </div>
          ),
        )}
      </nav>

      <div className="border-t border-vajra-border p-3">
        <div className="truncate text-[11px] text-slate-400" title={user?.email}>{user?.email}</div>
        <button onClick={() => void logout()} className="mt-1 text-[11px] text-slate-500 hover:text-rose-300">Sign out</button>
      </div>
    </aside>
  );
}
