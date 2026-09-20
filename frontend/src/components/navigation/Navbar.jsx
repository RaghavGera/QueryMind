import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { cn } from "../../lib/utils";
import Button from "../ui/Button";

const links = [
  { to: "/product", label: "Product" },
  { to: "/architecture", label: "How it works" },
  { to: "/developers", label: "Developers" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled ? "glass-strong shadow-card" : "bg-transparent border-b border-transparent"
      )}
    >
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="font-display text-lg font-semibold tracking-tight text-ink">
          QueryMind
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                cn(
                  "rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive ? "text-ink" : "text-ink-dim hover:text-ink"
                )
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Button as={Link} to="/app" variant="ghost" className="hidden sm:inline-flex">
            Sign in
          </Button>
          <Button as={Link} to="/app" variant="primary">
            Get started
          </Button>
        </div>
      </nav>
    </header>
  );
}
