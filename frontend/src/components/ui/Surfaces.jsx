import { cn } from "../../lib/utils";

export function Card({ className, children, ...props }) {
  return (
    <div className={cn("surface-card", className)} {...props}>
      {children}
    </div>
  );
}

export function StatusDot({ tone = "success", pulse = false }) {
  const tones = {
    success: "bg-state-success",
    warning: "bg-state-warning",
    danger: "bg-state-danger",
    idle: "bg-ink-faint",
    accent: "bg-accent-violet",
  };
  return (
    <span
      className={cn(
        "status-dot",
        tones[tone],
        pulse && "animate-pulse-glow"
      )}
    />
  );
}

export function Badge({ tone = "idle", children }) {
  const tones = {
    success: "text-state-success border-state-success/30 bg-state-success/10",
    warning: "text-state-warning border-state-warning/30 bg-state-warning/10",
    danger: "text-state-danger border-state-danger/30 bg-state-danger/10",
    idle: "text-ink-dim border-line bg-white/[0.03]",
    accent: "text-accent-glow border-accent-violet/30 bg-accent-violet/10",
  };
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}
