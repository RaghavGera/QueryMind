import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { LogOut } from "lucide-react";
import { useAuth, useUsage } from "../../auth/AuthProvider";
import { cn } from "../../lib/utils";

function Avatar({ user, size = 28 }) {
  const [broken, setBroken] = useState(false);
  const initial = (user?.name || user?.email || "?").trim().charAt(0).toUpperCase();
  if (user?.picture && !broken) {
    return (
      <img
        src={user.picture}
        alt=""
        width={size}
        height={size}
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
        className="rounded-full border border-white/10"
      />
    );
  }
  return (
    <span className="flex items-center justify-center rounded-full bg-accent-violet/30 font-display text-xs text-ink" style={{ width: size, height: size }}>
      {initial}
    </span>
  );
}

/** Signed-in user, today's question count, and sign-out. */
export default function AccountMenu() {
  const { user, signOut } = useAuth();
  const usage = useUsage();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => !ref.current?.contains(event.target) && setOpen(false);
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  const used = usage?.used ?? 0;
  const limit = usage?.limit;
  const nearLimit = limit != null && used >= limit - 2;

  const leave = async () => {
    setOpen(false);
    await signOut().catch(() => {});
    navigate("/", { replace: true });
  };

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3 transition-colors hover:bg-white/[0.05]" aria-haspopup="menu" aria-expanded={open}>
        <Avatar user={user} />
        {limit != null && (
          <span className={cn("font-mono text-[11px] tabular-nums", nearLimit ? "text-accent-amber" : "text-ink-dim")} title="Questions asked today (resets 00:00 UTC)">
            {used} / {limit}
          </span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="hud absolute right-0 z-50 mt-2 w-64 p-4"
          >
            <div className="flex items-center gap-3">
              <Avatar user={user} size={36} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{user?.name || "Signed in"}</p>
                <p className="truncate text-xs text-ink-faint">{user?.email}</p>
              </div>
            </div>
            {limit != null && (
              <div className="mt-4">
                <div className="flex justify-between font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint">
                  <span>Questions today</span>
                  <span className="tabular-nums">{used} / {limit}</span>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={cn("h-full rounded-full", nearLimit ? "bg-accent-amber" : "bg-gradient-to-r from-accent-violet to-accent-cyan")}
                    style={{ width: `${Math.min(100, (used / Math.max(1, limit)) * 100)}%` }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-ink-faint">Resets at 00:00 UTC.</p>
              </div>
            )}
            <button onClick={leave} role="menuitem" className="btn-ghost mt-4 w-full justify-start">
              <LogOut size={14} /> Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
