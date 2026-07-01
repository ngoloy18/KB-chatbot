import {
  ChevronDown,
  FileText,
  LockKeyhole,
  LogOut,
  MessageSquare,
  Plus,
  Upload,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { authApi, healthApi } from "../api/client.js";
import { BrandMark } from "../components/BrandMark.jsx";
import { clearAuth, getCurrentUser, saveCurrentUser } from "../utils/auth.js";
import { initials } from "../utils/format.js";

const mainNav = [
  { label: "Chat", to: "/chat", icon: MessageSquare },
  { label: "Documents", to: "/documents", icon: FileText },
];

const adminNav = [
  { label: "Users", to: "/admin/users", icon: Users },
];

function SidebarLink({ item }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) => `sidebar-link ${isActive ? "sidebar-link-active" : ""}`}
    >
      <Icon size={18} />
      <span>{item.label}</span>
    </NavLink>
  );
}

export function AppShell() {
  const navigate = useNavigate();
  const [user, setUser] = useState(getCurrentUser());
  const [health, setHealth] = useState("checking");

  useEffect(() => {
    authApi.me()
      .then((profile) => {
        saveCurrentUser(profile);
        setUser(profile);
      })
      .catch(() => {
        clearAuth();
        navigate("/login", { replace: true });
      });

    healthApi.check()
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
  }, [navigate]);

  const displayName = user?.full_name || user?.email || "Dev Nguyen";
  const roleLabel = user?.role === "admin" ? "Admin" : "User";
  const avatar = useMemo(() => initials(displayName), [displayName]);
  const isAdmin = user?.role === "admin";

  async function handleLogout() {
    try {
      await authApi.logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <div className="min-h-screen bg-med-bg text-med-text">
      <div className="grid min-h-screen grid-cols-[292px_minmax(0,1fr)] max-[1180px]:grid-cols-1">
        <aside className="flex min-h-0 flex-col gap-6 border-r border-med-border bg-white/70 px-5 py-7 backdrop-blur-xl max-[1180px]:border-b max-[1180px]:border-r-0">
          <BrandMark />

          <div className="min-h-0 flex-1 overflow-auto">
            <nav className="grid gap-2" aria-label="Main navigation">
              {mainNav.map((item) => <SidebarLink item={item} key={item.to} />)}
            </nav>
            {isAdmin && (
              <>
                <p className="mb-2 mt-6 px-3 text-xs font-black uppercase tracking-wide text-med-muted">Admin</p>
                <nav className="grid gap-2" aria-label="Admin navigation">
                  {adminNav.map((item) => <SidebarLink item={item} key={item.to} />)}
                </nav>
              </>
            )}
          </div>

          <section className="rounded-lg border border-med-border bg-white/80 p-4 shadow-soft">
            <h3 className="mb-3 text-sm font-black">Quick Actions</h3>
            <div className="grid gap-1">
              <button className="quick-action" type="button" onClick={() => navigate("/chat")}>
                <Plus size={16} /> New Chat <span>K</span>
              </button>
              {isAdmin && (
                <button className="quick-action" type="button" onClick={() => navigate("/documents")}>
                  <Upload size={16} /> Upload Document <span>U</span>
                </button>
              )}
            </div>
          </section>

          <section className="flex items-center gap-3 rounded-lg border border-med-border bg-white/80 p-4 shadow-soft">
            <span className="grid h-11 w-11 place-items-center rounded-full bg-med-primary text-sm font-black text-white">{avatar}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-black">{displayName}</p>
              <p className="text-sm text-med-muted">{roleLabel}</p>
            </div>
            <ChevronDown size={16} />
          </section>
        </aside>

        <main className="grid min-h-screen min-w-0 grid-rows-[auto_minmax(0,1fr)_auto]">
          <header className="flex min-h-[92px] flex-wrap items-center justify-between gap-4 border-b border-med-border bg-white/60 px-8 py-5 backdrop-blur-xl">
            <div>
              <p className="text-sm font-black uppercase tracking-wide text-med-primary">Developer knowledge base</p>
              <p className="mt-1 text-sm text-med-muted">Connected to your FastAPI backend contract.</p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-3">
              <button className="secondary-button" type="button" onClick={handleLogout}>
                <LogOut size={17} /> Logout
              </button>
            </div>
          </header>

          <section className="min-h-0 overflow-auto px-8 py-6 max-sm:px-4">
            <Outlet />
          </section>

          <footer className="flex min-h-11 flex-wrap items-center justify-between gap-3 border-t border-med-border bg-white/60 px-8 py-3 text-xs text-med-muted">
            <span className="flex items-center gap-2 font-bold text-med-primary"><LockKeyhole size={14} /> Secure - HIPAA-aware - Developer-focused</span>
            <span className="flex items-center gap-2">
              v1.2.0 - API {health}
              <span className={`h-2.5 w-2.5 rounded-full ${health === "online" ? "bg-med-success" : "bg-med-warning"}`} />
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
