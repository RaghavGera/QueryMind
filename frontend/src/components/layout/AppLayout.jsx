import { Suspense, useEffect, useState } from "react";
import { Link, useLocation, useOutlet } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Info, Menu, RotateCw, X } from "lucide-react";
import Sidebar, { ConnectionBadge } from "../navigation/Sidebar";
import BootScreen from "../ui/BootScreen";
import { useBackendInfo } from "../../hooks/useBackendInfo";
import { useAuth } from "../../auth/AuthProvider";
import { fetchUsage } from "../../services/queryApi";
import AccountMenu from "../navigation/AccountMenu";
import WorkspaceSwitcher from "../navigation/WorkspaceSwitcher";
import { useWorkspaces, workspaces } from "../../hooks/useWorkspaces";

/**
 * The app shell. Same look as the site, but motion stays quick (≤ 200 ms
 * between pages) and there is no WebGL or smooth scrolling here.
 */
export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { activeId, notice } = useWorkspaces();
  const backend = useBackendInfo(activeId);
  const location = useLocation();
  const outlet = useOutlet();
  const { status } = useAuth();

  // Signed-out visitors get a few free questions a day; show how many are left.
  useEffect(() => {
    if (status === "signedOut") fetchUsage().catch(() => {});
  }, [status]);

  if (status === "checking") return <BootScreen />;

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
        <header className="relative z-30 flex h-16 shrink-0 items-center justify-between border-b border-white/[0.06] bg-base-950/40 px-4 backdrop-blur-xl sm:px-6">
          <button onClick={() => setMobileOpen(true)} className="btn-ghost !px-1.5 md:hidden" aria-label="Open menu">
            <Menu size={18} />
          </button>
          <WorkspaceSwitcher tables={backend.schema?.tables.length ?? null} />
          <div className="flex items-center gap-3 text-ink-dim">
            <span className="hidden sm:inline-flex">
              <ConnectionBadge backend={backend} showDatabase={false} />
            </span>
            {status === "signedIn" ? (
              <AccountMenu />
            ) : (
              // Come back to the same page, query string included, after signing in.
              <Link to={`/signin?next=${encodeURIComponent(location.pathname + location.search)}`} className="btn-secondary !px-4 !py-1.5">
                Sign in
              </Link>
            )}
            {backend.status === "unreachable" && (
              <button onClick={backend.retry} className="btn-ghost !px-2 !py-1 text-xs" title={backend.error || undefined}>
                <RotateCw size={13} /> Retry
              </button>
            )}
          </div>
        </header>

        {notice && (
          <div className="flex items-start justify-between gap-3 border-b border-accent-amber/20 bg-accent-amber/10 px-4 py-2 text-sm text-ink sm:px-6">
            <span className="flex items-start gap-2">
              <Info size={15} className="mt-0.5 shrink-0 text-accent-amber" />
              {notice}
            </span>
            <button onClick={workspaces.dismissNotice} className="btn-ghost !p-1" aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        )}

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
