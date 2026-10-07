import ScrambleText from "../../motion/ScrambleText";

/** App page header: HUD label + decoding title + one line of detail. */
export default function PageHeader({ label, title, detail, children }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="hud-label mb-3">{label}</p>
        <ScrambleText as="h1" text={title} trigger="mount" duration={700} className="display-md block" innerClassName="text-gradient" />
        {detail && <p className="mt-2 text-sm text-ink-dim">{detail}</p>}
      </div>
      {children}
    </div>
  );
}
