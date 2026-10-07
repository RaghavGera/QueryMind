import { Link, NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Database, History, Bookmark, Settings, ChevronsLeft, ChevronsRight, X } from "lucide-react";
import { cn } from "../../lib/utils";
import Logo from "../ui/Logo";
import { StatusDot } from "../ui/Surfaces";

const items = [
  { to: "/app", label: "Ask", icon: MessageSquare, end: true },
  { to: "/app/schema", label: "Schema", icon: Database },
  { to: "/app/history", label: "Query History", icon: History },
  { to: "/app/saved", label: "Saved Queries", icon: Bookmark },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

function NavItems({ collapsed, onNavigate }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          title={collapsed ? label : undefined}
          className={({ isActive }) =>
            cn(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
              collapsed && "justify-center",
              isActive ? "text-ink" : "text-ink-dim hover:bg-white/[0.03] hover:text-ink",
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <motion.span
                  layoutId="sidebar-active"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  className="absolute inset-0 rounded-xl border border-accent-violet/20 bg-gradient-to-r from-accent-violet/[0.16] to-transparent"
                >
                  <span className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-accent-cyan shadow-[0_0_12px_rgba(94,234,212,0.9)]" />
                </motion.span>
              )}
              <Icon size={17} className={cn("relative shrink-0 transition-colors", isActive && "text-accent-cyan")} />
              {!collapsed && <span className="relative">{label}</span>}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

/** Real connection state from the backend (see hooks/useBackendInfo). */
export function ConnectionBadge({ backend, compact = false, showDatabase = true }) {
  const tone = backend.status === "connected" ? "success" : backend.status === "unreachable" ? "danger" : "idle";
  let label = "Connecting…";
  if (backend.status === "unreachable") label = "Unreachable";
  else if (backend.status === "connected") label = showDatabase ? backend.schema?.database || "Connected" : "Connected";
  return (
    <span className="flex min-w-0 items-center gap-2" title={backend.error || undefined}>
      <StatusDot tone={tone} pulse={backend.status === "connected"} />
      {!compact && <span className="truncate font-mono text-[11px] uppercase tracking-[0.16em]">{label}</span>}
    </span>
  );
}

export default function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile, backend }) {
  return (
    <>
      {/* Desktop */}
      <aside
        className={cn(
          "relative hidden shrink-0 flex-col border-r border-white/[0.06] bg-base-950/60 backdrop-blur-xl md:flex",
          "transition-[width] duration-200",
          collapsed ? "w-[68px]" : "w-60",
        )}
      >
        <div className={cn("flex h-16 items-center px-4", collapsed ? "justify-center" : "justify-between")}>
          {!collapsed && (
            <Link to="/" aria-label="QueryMind home">
              <Logo />
            </Link>
          )}
          <button onClick={onToggleCollapse} className="btn-ghost !px-1.5" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </button>
        </div>
        <NavItems collapsed={collapsed} />
        <div className={cn("border-t border-white/[0.06] p-4 text-ink-faint", collapsed && "flex justify-center")}>
          <ConnectionBadge backend={backend} compact={collapsed} />
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-white/[0.06] bg-base-950 md:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 300, damping: 32 }}
            >
              <div className="flex h-16 items-center justify-between px-4">
                <Link to="/" onClick={onCloseMobile} aria-label="QueryMind home">
                  <Logo />
                </Link>
                <button onClick={onCloseMobile} className="btn-ghost !px-1.5" aria-label="Close menu">
                  <X size={16} />
                </button>
              </div>
              <NavItems collapsed={false} onNavigate={onCloseMobile} />
              <div className="border-t border-white/[0.06] p-4 text-ink-faint">
                <ConnectionBadge backend={backend} />
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
