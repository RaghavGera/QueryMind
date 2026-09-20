import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export default function SchemaRelationships({ relationships }) {
  return (
    <div className="surface-card p-5">
      <h3 className="mb-3 text-sm font-medium text-ink">Relationships</h3>
      <ul className="space-y-2">
        {relationships.map((rel, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex items-center gap-2 rounded-lg border border-line bg-white/[0.02] px-3 py-2 text-sm"
          >
            <span className="mono text-ink">{rel.from}</span>
            <ArrowRight size={13} className="shrink-0 text-accent-glow" />
            <span className="mono text-ink">{rel.to}</span>
            <span className="ml-auto chip">{rel.label}</span>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
