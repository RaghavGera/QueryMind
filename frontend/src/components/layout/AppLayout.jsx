import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Menu } from "lucide-react";
import Sidebar from "../navigation/Sidebar";
import { StatusDot } from "../ui/Surfaces";

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-base-950">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-line px-4 sm:px-6">
          <button onClick={() => setMobileOpen(true)} className="btn-ghost !px-1.5 md:hidden">
            <Menu size={18} />
          </button>
          <span className="hidden text-sm text-ink-dim md:inline">Workspace: sample_ecommerce_db</span>
          <div className="flex items-center gap-2 text-sm text-ink-dim">
            <StatusDot tone="success" pulse />
            Operational
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
