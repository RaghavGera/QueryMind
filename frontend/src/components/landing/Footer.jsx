import { Link } from "react-router-dom";
import Logo from "../ui/Logo";

const links = [
  { to: "/product", label: "Product" },
  { to: "/architecture", label: "How it works" },
  { to: "/developers", label: "Developers" },
  { to: "/app", label: "Open app" },
];

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-white/[0.06] bg-base-950/70 px-6 py-12 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-xs text-sm text-ink-dim">
            Plain English in, parameterized SQL out. Asks when your question could mean two things.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {links.map((l) => (
            <Link key={l.to} to={l.to} className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-dim transition-colors hover:text-ink">
              {l.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="mx-auto mt-10 flex max-w-6xl flex-col gap-2 border-t border-white/[0.05] pt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint sm:flex-row sm:justify-between">
        <span>PostgreSQL · Gemini &amp; Groq</span>
        <span>© {new Date().getFullYear()} QueryMind</span>
      </div>
    </footer>
  );
}
