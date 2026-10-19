import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Database, FileUp, Trash2 } from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { useWorkspaces, workspaces } from "../../hooks/useWorkspaces";
import { forgetSchema } from "../../services/schemaApi";
import { DEMO_ID, expiresIn } from "../../services/workspaces.js";
import { cn } from "../../lib/utils";

const KIND = { demo: "Sample store · read-only", upload: "Your uploaded files", connection: "Your PostgreSQL" };

/** Which data questions go to: the demo store or your own workspace. */
export default function WorkspaceSwitcher({ tables }) {
  const { list, activeId } = useWorkspaces();
  const { status } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [problem, setProblem] = useState(null);
  const ref = useRef(null);
  const active = list.find((w) => w.id === activeId) || list[0];
  const own = list.find((w) => w.id !== DEMO_ID) || null;

  const close = () => {
    setOpen(false);
    setConfirming(false);
    setProblem(null);
  };

  useEffect(() => {
    if (!open) return undefined;
    const outside = (event) => {
      if (!ref.current?.contains(event.target)) {
        setOpen(false);
        setConfirming(false);
        setProblem(null);
      }
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  const choose = (id) => {
    workspaces.setActive(id);
    close();
  };

  const remove = async () => {
    try {
      await workspaces.remove(own.id);
      forgetSchema(own.id);
      close();
    } catch (error) {
      setProblem(error.message);
    }
  };

  return (
    <div ref={ref} className="relative min-w-0">
      <button
        onClick={() => (open ? close() : setOpen(true))}
        className="flex min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-faint transition-colors hover:bg-white/[0.04]"
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Choose which data to ask"
      >
        <Database size={13} className={active?.id === DEMO_ID ? "text-ink-faint" : "text-accent-cyan"} />
        <span className="hidden sm:inline">Workspace ·</span>
        <span className="truncate text-ink-dim">{active?.name || "—"}</span>
        {tables != null && <span className="hidden text-ink-faint lg:inline">· {tables} tables</span>}
        <ChevronDown size={13} className={cn("shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="listbox"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="hud absolute left-0 z-50 mt-2 w-80 p-2"
          >
            <p className="hud-label px-2 pb-2 pt-1">Ask about</p>
            {list.map((w) => (
              <button
                key={w.id}
                role="option"
                aria-selected={w.id === activeId}
                onClick={() => choose(w.id)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white/[0.05]",
                  w.id === activeId && "bg-white/[0.04]",
                )}
              >
                <Database size={15} className={cn("mt-0.5 shrink-0", w.id === DEMO_ID ? "text-ink-faint" : "text-accent-cyan")} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-ink">{w.name}</span>
                  <span className="block text-xs text-ink-faint">
                    {KIND[w.kind] || w.kind}
                    {w.expires_at && ` · ${expiresIn(w.expires_at)}`}
                  </span>
                </span>
                {w.id === activeId && <Check size={15} className="mt-0.5 shrink-0 text-accent-cyan" />}
              </button>
            ))}

            <div className="mt-1 border-t border-white/[0.06] pt-1">
              {status !== "signedIn" ? (
                <Link
                  to={`/signin?next=${encodeURIComponent(location.pathname)}`}
                  onClick={close}
                  className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm text-ink-dim hover:bg-white/[0.05] hover:text-ink"
                >
                  <FileUp size={15} /> Sign in to use your own data
                </Link>
              ) : (
                <Link
                  to="/app/connect"
                  onClick={close}
                  className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm text-ink-dim hover:bg-white/[0.05] hover:text-ink"
                >
                  <FileUp size={15} /> {own ? "Replace with new files" : "Upload your data"}
                </Link>
              )}
              {own && !confirming && (
                <button
                  onClick={() => setConfirming(true)}
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm text-ink-dim hover:bg-white/[0.05] hover:text-state-danger"
                >
                  <Trash2 size={15} /> Delete {own.name}
                </button>
              )}
              {own && confirming && (
                <div className="rounded-lg bg-state-danger/10 px-2 py-2 text-sm">
                  <p className="text-ink">Delete {own.name} and its data? Your history stays.</p>
                  <div className="mt-2 flex gap-2">
                    <button onClick={remove} className="btn-ghost !px-2 !py-1 text-state-danger">Delete</button>
                    <button onClick={() => setConfirming(false)} className="btn-ghost !px-2 !py-1">Keep it</button>
                  </div>
                </div>
              )}
              {problem && <p className="px-2 py-1 text-xs text-state-danger">{problem}</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
