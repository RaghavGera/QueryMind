import { ShieldCheck, DatabaseZap, Ban, ScrollText, Lock, KeyRound } from "lucide-react";
import { trustPoints } from "../../data/mockData";

const icons = [ShieldCheck, DatabaseZap, Ban, ScrollText, Lock, KeyRound];

export default function TrustSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 sm:px-6 py-24">
      <div className="mb-10 text-center">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">Trust</p>
        <h2 className="font-display text-3xl font-semibold text-ink">Built to touch a real database safely</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {trustPoints.map((point, i) => {
          const Icon = icons[i % icons.length];
          return (
            <div key={point.title} className="surface-card p-5 transition-transform hover:-translate-y-1">
              <Icon size={20} className="mb-3 text-accent-glow" />
              <h3 className="mb-1.5 text-sm font-medium text-ink">{point.title}</h3>
              <p className="text-sm leading-relaxed text-ink-dim">{point.detail}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
