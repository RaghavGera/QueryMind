import { cn } from "../../lib/utils";

/** The QueryMind mark: a faceted diamond with a glowing core. */
export function LogoMark({ size = 22, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className={cn("shrink-0", className)} aria-hidden="true">
      <defs>
        <linearGradient id="qm-g" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c9c2ff" />
          <stop offset="0.55" stopColor="#8b7bff" />
          <stop offset="1" stopColor="#5eead4" />
        </linearGradient>
        <radialGradient id="qm-core" cx="16" cy="16" r="5" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="#5eead4" stopOpacity="0" />
        </radialGradient>
      </defs>
      <path d="M16 2 30 16 16 30 2 16Z" stroke="url(#qm-g)" strokeWidth="1.6" />
      <path d="M16 8 24 16 16 24 8 16Z" fill="url(#qm-g)" opacity="0.25" />
      <path d="M2 16h28M16 2v28" stroke="url(#qm-g)" strokeWidth="0.8" opacity="0.45" />
      <circle cx="16" cy="16" r="5" fill="url(#qm-core)" />
    </svg>
  );
}

export default function Logo({ className }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="font-display text-[17px] font-semibold tracking-tight text-ink">QueryMind</span>
    </span>
  );
}
