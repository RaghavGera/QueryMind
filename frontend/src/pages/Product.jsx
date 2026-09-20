import Navbar from "../components/navigation/Navbar";
import Footer from "../components/landing/Footer";
import { Card } from "../components/ui/Surfaces";
import { MessageSquare, ShieldQuestion, Code2, LineChart } from "lucide-react";

const features = [
  { icon: MessageSquare, title: "Ask in plain language", detail: "No SQL required. Describe what you want to know, the way you'd ask a colleague." },
  { icon: ShieldQuestion, title: "Clarifies instead of guessing", detail: "When a question is genuinely ambiguous, QueryMind asks a targeted question instead of returning the wrong answer confidently." },
  { icon: Code2, title: "Transparent SQL", detail: "Every answer comes with the exact, parameterized SQL that produced it — copyable, explainable, re-runnable." },
  { icon: LineChart, title: "Results that make sense", detail: "Tables when you need detail, charts when you need a trend — switch between them instantly." },
];

export default function Product() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="mx-auto max-w-4xl px-6 pb-16 pt-36 text-center">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">Product</p>
        <h1 className="font-display text-4xl font-semibold text-ink">A database interface that thinks before it queries</h1>
      </section>
      <section className="mx-auto grid max-w-5xl gap-4 px-6 pb-28 sm:grid-cols-2">
        {features.map(({ icon: Icon, title, detail }) => (
          <Card key={title} className="p-6">
            <Icon size={20} className="mb-3 text-accent-glow" />
            <h3 className="mb-1.5 text-base font-medium text-ink">{title}</h3>
            <p className="text-sm leading-relaxed text-ink-dim">{detail}</p>
          </Card>
        ))}
      </section>
      <Footer />
    </div>
  );
}
