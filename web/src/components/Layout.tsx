import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  ChevronRight,
  FileClock,
  FolderKanban,
  GitPullRequestArrow,
  LogOut,
  Menu,
  Settings,
  Workflow,
  X
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";

const navigation = [
  { to: "/overview", label: "Overview", icon: Activity },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/changes", label: "Changes", icon: GitPullRequestArrow },
  { to: "/jobs", label: "Execution jobs", icon: Workflow },
  { to: "/audit", label: "Audit trail", icon: FileClock }
];

export function Layout() {
  const auth = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });

  return (
    <div className="app-shell">
      <button className="mobile-menu" type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
        <Menu size={21} />
      </button>
      {mobileOpen && <button className="nav-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark" aria-hidden="true"><Boxes size={20} /></div>
          <div><strong>VersionWeaver</strong><span>Operations console</span></div>
          <button className="mobile-close" type="button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={19} /></button>
        </div>
        <nav aria-label="Primary navigation">
          <p className="nav-label">Workspace</p>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              <Icon size={18} />
              <span>{label}</span>
              <ChevronRight className="nav-chevron" size={15} />
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            <Settings size={18} /><span>Connection</span><ChevronRight className="nav-chevron" size={15} />
          </NavLink>
          <button className="nav-link" type="button" onClick={auth.logout}>
            <LogOut size={18} /><span>Disconnect</span>
          </button>
        </div>
      </aside>
      <main className="main-area">
        <div className="topbar">
          <div>
            <span className="topbar-path">Console</span>
            <span className="topbar-separator">/</span>
            <span>{navigation.find((item) => location.pathname.startsWith(item.to))?.label ?? "Connection"}</span>
          </div>
          <div className="connection-pill">
            <span className={`pulse-dot ${health.data?.status === "ok" ? "online" : "offline"}`} />
            {health.isPending ? "Checking API" : health.data?.status === "ok" ? `API v${health.data.version}` : "API degraded"}
          </div>
        </div>
        <div className="page-content"><Outlet /></div>
      </main>
    </div>
  );
}
