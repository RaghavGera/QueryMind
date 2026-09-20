import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="border-t border-line px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <span className="font-display text-sm font-semibold text-ink">QueryMind</span>
        <div className="flex gap-5 text-sm text-ink-dim">
          <Link to="/architecture" className="hover:text-ink">Architecture</Link>
          <Link to="/developers" className="hover:text-ink">Developers</Link>
          <Link to="/app" className="hover:text-ink">Sign in</Link>
        </div>
        <span className="text-xs text-ink-faint">© {new Date().getFullYear()} QueryMind</span>
      </div>
    </footer>
  );
}
