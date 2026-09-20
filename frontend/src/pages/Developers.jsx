import Navbar from "../components/navigation/Navbar";
import Footer from "../components/landing/Footer";
import SqlPanel from "../components/sql/SqlPanel";
import { Card } from "../components/ui/Surfaces";
import { Webhook, KeyRound, Database, BookOpen } from "lucide-react";

const codeSample = `const result = await querymind.query({
  question: "How many customers signed up last month?",
});

console.log(result.sql);
console.log(result.rows);`;

const items = [
  { icon: KeyRound, title: "Authentication", detail: "Scoped API keys per workspace, rotated on demand." },
  { icon: Database, title: "SQL dialects", detail: "PostgreSQL today; MySQL and Snowflake on the roadmap." },
  { icon: Webhook, title: "Webhooks", detail: "Get notified when a scheduled query completes or fails." },
  { icon: BookOpen, title: "Documentation", detail: "Full API reference, SDK guides, and query cookbook." },
];

export default function Developers() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="mx-auto max-w-4xl px-6 pb-10 pt-36">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-accent-glow">Developers</p>
        <h1 className="font-display text-4xl font-semibold text-ink">Query your database from code</h1>
        <p className="mt-3 max-w-xl text-ink-dim">
          The same engine behind the product, available as an API and a lightweight SDK.
        </p>
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-16">
        <SqlPanel sql={codeSample} dialect="JavaScript" />
      </section>

      <section className="mx-auto grid max-w-4xl gap-4 px-6 pb-28 sm:grid-cols-2">
        {items.map(({ icon: Icon, title, detail }) => (
          <Card key={title} className="p-5">
            <Icon size={18} className="mb-3 text-accent-glow" />
            <h3 className="mb-1.5 text-sm font-medium text-ink">{title}</h3>
            <p className="text-sm text-ink-dim">{detail}</p>
          </Card>
        ))}
      </section>
      <Footer />
    </div>
  );
}
