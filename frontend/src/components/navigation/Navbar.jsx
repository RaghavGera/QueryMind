import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { useLaunch } from "../../motion/warp";
import Magnetic from "../../motion/Magnetic";
import Logo from "../ui/Logo";

const links = [
  { to: "/product", label: "Product" },
  { to: "/architecture", label: "How it works" },
  { to: "/developers", label: "Developers" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const launch = useLaunch();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-500",
        scrolled || menuOpen
          ? "border-b border-white/[0.06] bg-base-950/55 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent",
      )}
    >
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" onClick={() => setMenuOpen(false)} aria-label="QueryMind home">
          <Logo />
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                cn(
                  "group relative rounded-lg px-3.5 py-2 font-mono text-[11px] uppercase tracking-[0.2em] transition-colors",
                  isActive ? "text-ink" : "text-ink-dim hover:text-ink",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {l.label}
                  <span
                    className={cn(
                      "absolute inset-x-3.5 -bottom-0.5 h-px origin-left bg-gradient-to-r from-accent-violet to-accent-cyan transition-transform duration-300",
                      isActive ? "scale-x-100" : "scale-x-0 group-hover:scale-x-100",
                    )}
                  />
                </>
              )}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Link to="/app" className="btn-ghost hidden sm:inline-flex">
            Open app
          </Link>
          <Magnetic className="hidden sm:inline-block">
            <button onClick={() => launch("/app")} className="btn-primary !px-5 !py-2.5">
              Launch <ArrowUpRight size={15} />
            </button>
          </Magnetic>
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="btn-ghost !px-2 md:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden border-t border-white/[0.06] md:hidden"
          >
            <div className="flex flex-col gap-1 px-4 py-4">
              {links.map((l, i) => (
                <motion.div key={l.to} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.04 * i }}>
                  <NavLink
                    to={l.to}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "block rounded-lg px-3 py-3 font-mono text-xs uppercase tracking-[0.2em]",
                        isActive ? "bg-white/[0.06] text-ink" : "text-ink-dim hover:bg-white/[0.03] hover:text-ink",
                      )
                    }
                  >
                    {l.label}
                  </NavLink>
                </motion.div>
              ))}
              <button
                onClick={() => {
                  setMenuOpen(false);
                  launch("/app");
                }}
                className="btn-primary mt-2"
              >
                Launch QueryMind <ArrowUpRight size={15} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
