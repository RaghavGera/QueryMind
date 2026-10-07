import { Suspense, useState } from "react";
import { useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, RotateCw } from "lucide-react";
import Sidebar, { ConnectionBadge } from "../navigation/Sidebar";
import BootScreen from "../ui/BootScreen";
import { useBackendInfo } from "../../hooks/useBackendInfo";

/**
 * The app shell. Same look as the site, but motion stays quick (≤ 200 ms
 * between pages) and there is no WebGL or smooth scrolling here.
 */
export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const backend = useBackendInfo();
  const location = useLocation();
  const outlet = useOutlet();

  return (
    <div className="relative flex h-svh overflow-hidden bg-base-950">
      {/* Slow aurora behind everything (CSS only). */}
      <div className="fx-nebula opacity-60" aria-hidden="true" />

      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        backend={backend}
      />

      <div className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/[0.06] bg-base-950/40 px-4 backdrop-blur-xl sm:px-6">
          <button onClick={() => setMobileOpen(true)} className="btn-ghost !px-1.5 md:hidden" aria-label="Open menu">
            <Menu size={18} />
          </button>
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.2em] text-ink-faint md:inline">
            Workspace · <span className="text-ink-dim">{backend.schema?.database || "—"}</span>
            {backend.schema && <span className="text-ink-faint"> · {backend.schema.tables.length} tables</span>}
          </span>
          <div className="flex items-center gap-3 text-ink-dim">
            <ConnectionBadge backend={backend} showDatabase={false} />
            {backend.status === "unreachable" && (
              <button onClick={backend.retry} className="btn-ghost !px-2 !py-1 text-xs" title={backend.error || undefined}>
                <RotateCw size={13} /> Retry
              </button>
            )}
          </div>
        </header>

        <main className="relative flex-1 overflow-y-auto">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <Suspense fallback={<BootScreen />}>{outlet}</Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
