import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearApiKey } from "../api";

interface NavItem {
  to: string;
  icon: string;
  label: string;
  exact?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",              icon: "upload_file", label: "New Audit",    exact: true },
  { to: "/jobs",          icon: "history",     label: "Audit Log" },
  { to: "/guidelines",    icon: "policy",      label: "Policies" },
  { to: "/integrations",  icon: "hub",         label: "Integrations" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen bg-obs-bg text-vio-text font-sans">
      {/* Sidebar */}
      <aside
        className="h-screen w-64 fixed left-0 top-0 overflow-y-auto flex flex-col gap-8 p-6 z-50"
        style={{
          background: "linear-gradient(to right, #221536, #1a0c2d)",
          boxShadow: "40px 0 60px -15px rgba(237,220,255,0.08)",
        }}
      >
        {/* Brand */}
        <div className="flex flex-col gap-1">
          <span className="text-violet-200 font-black italic tracking-tighter text-lg leading-none">
            The Obsidian Lens
          </span>
          <span className="text-[11px] tracking-[0.05rem] uppercase text-vio-text/40 font-semibold">
            Brand Compliance
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = item.exact
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`px-4 py-3 flex items-center gap-3 rounded-lg transition-all duration-200 active:scale-[0.97] ${
                  isActive
                    ? "bg-obs-top text-vio shadow-[inset_0_0_10px_rgba(195,193,255,0.2)]"
                    : "text-vio-text/60 hover:text-vio-text hover:bg-obs-bright/50 inner-glow"
                }`}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>
                  {item.icon}
                </span>
                <span className="font-medium text-sm">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* CTA + key */}
        <div className="mt-auto pt-6 space-y-3" style={{ borderTop: "1px solid rgba(70,69,86,0.15)" }}>
          <Link
            to="/"
            className="w-full py-3 px-4 font-bold rounded-xl flex items-center justify-center gap-2 transition-all active:scale-95 text-[#0e006a] text-sm"
            style={{ background: "linear-gradient(135deg, #c3c1ff, #5b53ff)" }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add_circle</span>
            New Audit
          </Link>
          <button
            onClick={() => { clearApiKey(); navigate("/setup"); }}
            className="w-full py-2 text-[11px] text-muted/40 hover:text-muted flex items-center justify-center gap-1.5 transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: "13px" }}>key</span>
            Change API key
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 flex-1 min-h-screen">
        {children}
      </main>
    </div>
  );
}
