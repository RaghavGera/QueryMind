import { useId } from "react";
import { cn } from "../../lib/utils";

/**
 * The QueryMind mark: a Q whose tail is a glowing query beam, on a nebula
 * tile. Same drawing as public/favicon.svg; keep the two in step.
 */
export function LogoMark({ size = 22, className }) {
  // Unique ids: several marks on one page must not share gradients.
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={cn("shrink-0", className)} aria-hidden="true">
      <defs>
        <radialGradient id={`${id}n`} cx="30%" cy="22%" r="85%">
          <stop stopColor="#4c2fb0" />
          <stop offset=".55" stopColor="#1a1440" />
          <stop offset="1" stopColor="#0a0916" />
        </radialGradient>
        <linearGradient id={`${id}g`} x1="12" y1="10" x2="48" y2="50" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ddd6fe" />
          <stop offset=".5" stopColor="#9b8cff" />
          <stop offset="1" stopColor="#5eead4" />
        </linearGradient>
        <filter id={`${id}glow`} filterUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
          <feGaussianBlur stdDeviation="2.2" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#${id}n)`} />
      <circle cx="50" cy="13" r="1.4" fill="#fff" opacity=".8" />
      <circle cx="12" cy="50" r="1.1" fill="#fff" opacity=".6" />
      <circle cx="54" cy="30" r="1" fill="#5eead4" opacity=".8" />
      <circle cx="29" cy="29" r="15" fill="none" stroke={`url(#${id}g)`} strokeWidth="7.5" />
      <path d="M37 37 50 50" stroke="#5eead4" strokeWidth="7" strokeLinecap="round" filter={`url(#${id}glow)`} />
      <path d="M52 44Q52 50 58 50Q52 50 52 56Q52 50 46 50Q52 50 52 44Z" fill="#fff" filter={`url(#${id}glow)`} />
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
