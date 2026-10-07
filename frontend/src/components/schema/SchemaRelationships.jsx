import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export default function SchemaRelationships({ relationships }) {
  return (
    <div className="hud p-5">
      <h3 className="mb-3 font-mono text-[11px] uppercase tracking-[0.2em] text-accent-cyan">Foreign keys</h3>
      {relationships.length === 0 ? (
        <p className="text-sm text-ink-dim">No foreign keys in this schema.</p>
      ) : (
        <ul className="space-y-2">
          {relationships.map((rel, i) => (
            <motion.li
              key={`${rel.from}-${rel.label}`}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-sm"
            >
              <span className="font-mono text-ink">{rel.from}</span>
              <ArrowRight size={13} className="shrink-0 text-accent-cyan" />
              <span className="font-mono text-ink">{rel.to}</span>
              <span className="chip ml-auto font-mono">{rel.label}</span>
            </motion.li>
          ))}
        </ul>
      )}
    </div>
  );
}
