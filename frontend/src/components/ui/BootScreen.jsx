import { LogoMark } from "./Logo";

/** Shown while a page's code loads. */
export default function BootScreen() {
  return (
    <div className="flex h-svh flex-col items-center justify-center gap-4" role="status" aria-label="Loading">
      <LogoMark size={40} className="animate-pulse-glow" />
      <span className="hud-label">Booting</span>
    </div>
  );
}
