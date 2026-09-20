import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Database,
  History,
  Bookmark,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  X,
} from "lucide-react";
import { cn } from "../../lib/utils";

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
          className={({ isActive }) =>
            cn(
              "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
              isActive ? "bg-white/[0.06] text-ink" : "text-ink-dim hover:bg-white/[0.03] hover:text-ink"
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <motion.span
                  layoutId="sidebar-active"
                  className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-accent-violet"
                />
              )}
              <Icon size={17} className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile }) {
  return (
    <>
      {/* Desktop */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r border-line bg-base-900/60 backdrop-blur-xl md:flex",
          "transition-[width] duration-200",
          collapsed ? "w-[68px]" : "w-60"
        )}
      >
        <div className={cn("flex h-16 items-center px-4", collapsed ? "justify-center" : "justify-between")}>
          {!collapsed && <span className="font-display text-sm font-semibold text-ink">QueryMind</span>}
          <button onClick={onToggleCollapse} className="btn-ghost !px-1.5">
            {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </button>
        </div>
        <NavItems collapsed={collapsed} />
        <div className="border-t border-line p-3 text-xs text-ink-faint">
          {!collapsed && <span>Connected: sample_ecommerce_db</span>}
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
              className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-base-900 border-r border-line md:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 300, damping: 32 }}
            >
              <div className="flex h-16 items-center justify-between px-4">
                <span className="font-display text-sm font-semibold text-ink">QueryMind</span>
                <button onClick={onCloseMobile} className="btn-ghost !px-1.5">
                  <X size={16} />
                </button>
              </div>
              <NavItems collapsed={false} onNavigate={onCloseMobile} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
